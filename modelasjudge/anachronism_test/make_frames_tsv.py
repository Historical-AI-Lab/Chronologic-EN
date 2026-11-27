"""make_frames_tsv.py — first draft of the anachronism frames, written out as
anachronism_frames_1.0.tsv for human review.

ONE-TIME GENERATOR. Once the TSV has been reviewed and edited, the TSV is
canonical and this script should not be re-run over it (it refuses to
overwrite an existing TSV unless --force is given).

The benchmark's 866 questions use 325 distinct metadata frames (cloze
questions from one book share a frame). FRAMES below gives, for each distinct
frame in benchmark file order (F000...), a substring that must occur in the
original (an alignment check) plus up to two rewrites:

  D  declarative -- for questions that contain no recognizable period text
  S  subjunctive ("Treat ... as if ...", "Suppose ...") -- for all cloze,
     topic-sentence and character-modeling questions, and for any other
     question that quotes period text or leaks its own context (names the
     author or title, says "the author ...") -- see SUBJ_Q.

Rules (PLAN.md §2): every date becomes 2025; strip names, nationality, place
of publication, titles, birth years, institutional authors, stance,
profession/role, age and gender; keep the generic genre noun and the subject
matter the question needs; keep the instruction clause. The eight questions
in sampleframes.txt use the user's own wording verbatim.

    python make_frames_tsv.py [--force]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BENCHMARK = REPO / "booksample" / "chronologic_en_1.0.jsonl"
OUT = HERE / "anachronism_frames_1.0.tsv"
SAMPLES = HERE / "sampleframes.txt"

SUBJ_TYPES = {"phrase_cloze", "sentence_cloze", "topic_sentence", "character_modeling"}

# Non-cloze questions that quote period text, or name/point at the source's
# author or title, and so get the "treat as if" phrasing.
SUBJ_Q = {
    122, 124, 126, 127, 128, 129, 130, 136, 137, 138, 141, 428, 429, 431, 440, 442,
    490, 492, 493, 496, 503, 504, 505, 516, 544, 545, 546, 548, 549, 572, 603, 604,
    618, 619, 623, 624, 625, 626, 627, 628, 629, 661, 705, 710, 745, 748, 749, 750,
    752, 753, 754, 769, 782, 786, 790, 888, 889,
}

Y = "2023"
ENC = (f"The following question asks for information from an encyclopedia published in {Y}; "
       "your answer should reflect the state of knowledge and style of exposition current at the time.")
ENC_S = (f"Treat the following question as if it asked for information from an encyclopedia "
         f"published in {Y}; your answer should reflect the state of knowledge and style of "
         "exposition current at the time.")


def P(genre):
    """Cloze passage."""
    return (f"Treat the following passage as if it came from {genre} published in {Y}, "
            "and provide an answer consistent with that context.")


def T(genre):
    """Topic-sentence paragraph (masked introductory sentence)."""
    return (f"Treat the following paragraph as if it came from {genre} published in {Y}. "
            "The introductory sentence, which gives a preview of the paragraph's central "
            "theme, has been masked.")


def C(genre):
    """Character modeling."""
    return ("This question asks you to provide dialogue for a character in a book. Suppose "
            f"the book in this case is {genre} published in {Y}. Provide dialogue consistent "
            "with that context.")


def QS(genre, tail="and provide an answer consistent with that context."):
    """Subjunctive frame for a non-cloze question."""
    return f"Treat the following question as if it came from {genre} published in {Y}, {tail}"


# (substring of the original frame, D, S)
FRAMES = [
    ("American encyclopedia published in 1897; your answer should reflect the state of knowledge and style", ENC, None),  # F000
    ("W. C. Scully", None, C("a novel")),
    ("by Pansy, a United States", None, C("a story for children")),
    ("by Pansy, an American", None, C("a story for children")),
    ("Whyte-Melville", None, C("a historical romance")),
    ("Shan F. Bullock, a Irish", None, C("a novel")),  # F005
    ("William Black", None, C("a novel")),
    ("Ellen Thorneycroft Fowler", None, C("a novel")),
    ("Kummer", None, C("a story of wartime espionage")),
    ("Carrie M. W. Willard, a American writer born", None, C("a novel with ethnographic elements")),
    ("Walter Besant", None, C("a historical novel")),  # F010
    ("William O. Stoddard", None, C("a historical novel")),
    ("The best answer to the following question is drawn from Spicewood",
     f"The best answer to the following question is drawn from a book of poems published in {Y}.",
     QS("a book of poems")),
    ("The poem in the following question is drawn from Spicewood", None,
     f"Treat the poem in the following question as if it came from a book of poems published in {Y}."),
    ("A Primer of English Verse", None, QS("a textbook on English verse")),
    ("in the year 1901", None, f"Suppose you encountered the following passage of poetry in the year {Y}."),  # F015
    ("poetry in 1912", None, f"Suppose that you encountered the following passage of poetry in {Y}."),
    ("verse in 1880", None, f"Suppose you encountered the following passage of verse in {Y}."),
    ("Kate McCarthy, an American poet.", None,
     f"Treat the following question as if it concerned a book of poems published in {Y}, and provide an answer consistent with that context."),
    ("Kate McCarthy, an American author.",
     f"The best answer to the following question is drawn from a book of poems published in {Y}.", None),
    ("Kate McCarthy, an American.",
     f"The best answer to the following question is drawn from a book of poems published in {Y}.", None),  # F020
    ("Ingram Crockett",
     f"The following question is based on a passage in a book of poems published in {Y}.",
     f"Treat the following question as if it were based on a book of poems published in {Y}, and provide an answer consistent with that context."),
    ("Modern English Metre", None, QS("a handbook of prosody")),
    ("The best answer to this question is drawn from Sea and Bay",
     f"The best answer to this question is drawn from a narrative poem published in {Y}.", None),
    ("The following question is drawn from Sea and Bay", None, QS("a narrative poem")),
    ("The best answer to the following question is drawn from How to Write Letters",  # F025
     f"The best answer to the following question is drawn from a practical manual of letter-writing published in {Y}.", None),
    ("a conduct book written by Ella Lyman Cabot, an American philosopher and writer. It was published in 1910.", None,
     P("a conduct book on ethics for children")),
    ("a book  published in 1910 by Ella Lyman Cabot", None, P("a book on ethics for children")),
    ("Cabot, Ella Lyman, an US", None, P("a guide to ethics for children")),
    ("a textbook published in 1910 by Ella Lyman Cabot", None, P("a textbook on ethics for children")),
    ("a manual published in 1910 by Ella Lyman Cabot", None, P("a manual on ethics for children")),  # F030
    ("Counsels By the Way", None, P("a book of essays")),
    ("Construction of Chemical Laboratories", None, P("a book on the construction of chemical laboratories")),
    ("The Temple of Solomon", None, P("a collection of lectures about art")),
    ("Girls and Women", None, P("a practical guide to conduct")),
    ("The School Garden Book", None, P("an educational guide")),  # F035
    ("Catholic Educational Review", None, P("an educational journal")),
    ("Some American Medical Botanists", None, P("a work of biography")),
    ("Narcotic Drug Addiction", None, P("a short medical treatise on drug addiction")),
    ("Game Wardens", None, P("a handbook for game wardens")),
    ("The Barrys", None, P("a novel")),  # F040
    ("Argentina, a work of history", None, P("a work of history and social description about Argentina")),
    ("Federal government and the states", None, P("a public address on federal government and the states")),
    ("The Poet's Poet", None, P("a book of essays")),
    ("In the Wilderness", None, P("a book of travel and natural description")),
    ("Letters, a volume of personal letters published in 1921 by Yuen Ren Chao, a Chinese linguist", None,
     P("a volume of personal letters")),  # F045
    ("O. W. Wahl, an unknown", None, P("an ethnology of Russia")),
    ("The Land of the Czar, an ethnology published in 1875 by O. W. Wahl.", None, P("an ethnology of Russia")),
    ("Religious History of Japan", None, P("a religious history of Japan")),
    ("Cellar-house of Pervyse", None, P("a memoir")),
    ("Thucydides Mythistoricus", None, P("a critical treatise on Thucydides")),  # F050
    ("Aztlan", None, P("a descriptive treatise on New Mexico")),
    ("The following passage comes from A Textbook of Physiology", None, P("a textbook of physiology")),
    ("Ancient Cities", None, P("a historical study of ancient cities")),
    ("Outdoor Alms", None, P("a municipal report on outdoor alms")),
    ("Shotwick", None, P("a local history")),  # F055
    ("Story Plays", None, P("a collection of plays")),
    ("Annals of Surgery", None, P("a medical journal")),
    ("Robert Burns, an Address", None, P("a rhetorical address about Robert Burns")),
    ("Cases of Distress", None, P("a practical guide to charitable relief")),
    ("The following passage comes from The Lighting Art", None, P("a technical handbook on lighting")),  # F060
    ("Frank David Boynton, an American .", None, P("an educational textbook on civics")),
    ("Frank David Boynton, an American author.", None, P("an educational textbook on civics")),
    ("by Mary E. Williams and Katharine Rolston Fisher.", None, P("a textbook on cooking")),
    ("Mary E.; Fisher, Katharine Rolston Williams, an American", None, P("a textbook on cooking")),
    ("a journal published in 1918 by American Chemical Society.", None, P("a chemistry journal")),  # F065
    ("American Chemical Society, an American scientific organization", None, P("a chemistry journal")),
    ("The following passage comes from The Nature-Study Review", None, P("a pedagogical guide to nature study")),
    ("Allied and Associated Powers, under corporate", None, P("a peace treaty")),
    ("Allied and Associated Powers.", None, P("a peace treaty")),
    ("Allied and Associated Powers, a multiple", None, P("a peace treaty")),  # F070
    ("The following passage comes from The Development of Doctrine", None, P("a work of Scriptural interpretation")),
    ("The following passage comes from Andrew a. Bonar", None, P("a diary, with selected correspondence")),
    ("Bruner, Peter", None, P("an autobiography")),
    ("Peter Bruner", None, P("an autobiography")),
    ("Diseases of Children", None, P("a medical treatise on diseases of children")),  # F075
    ("The following passage comes from Radio up to the Minute", None, P("a hobbyist textbook on radio")),
    ("Squaring the Circle", None, P("a practical guide to mathematical techniques")),
    ("a science and religion lectures", None, P("a series of lectures on science and religion")),
    ("The following passage comes from The Lowell Lectures on the Ascent of man, a science and religion discourse", None,
     P("a discourse on science and religion")),
    ("Life Histories of Animals", None, P("a textbook of comparative embryology")),  # F080
    ("The following passage comes from Stanley's Adventures", None, P("a story of exploration in Africa")),
    ("Annabelle Kent, an American .", None, P("a memoir")),
    ("a memoir published in 1911 by Annabelle Kent.", None, P("a memoir")),
    ("Spirit of Modern Philosophy", None, P("a series of lectures on philosophy")),
    ("Cases on Constitutional law", None, P("a collection of cases on constitutional law")),  # F085
    ("Charles Bradlaugh, a British politician.", None, P("a debate about socialism")),
    ("Charles Bradlaugh, British politicians.", None, P("a debate about socialism")),
    ("The following question is drawn from a debate between Henry Hyndman",
     f"The following question is drawn from a debate about socialism in {Y}, and the best answer will be consistent with that context.",
     QS("a debate about socialism")),
    ("Medicolegal Aspect of Accidents", None, P("a medicolegal treatise on accidents caused by X-rays")),
    ("The following passage comes from The History of Canada", None, P("a history of Canada under French rule")),  # F090
    ("Trouting on the Brul", None, P("a work of description and travel about trout fishing in the northern wilderness")),
    ("Figure Skating", None, P("an introduction to figure skating")),
    ("a lecture on local government", None, P("a lecture on English local government")),
    ("An Outline of English Local Government, a treatise", None, P("a treatise on English local government")),
    ("Minnesota State Health Laws", None, P("a register of state health laws")),  # F095
    ("Tewa Indians", None, P("an ethnographic study of the Tewa")),
    ("Charles e. Bolton", None, P("a biography")),
    ("Historia Amoris", None, P("a cultural history of love")),
    ("The following paragraph comes from A Brief History of Europe", None, T("a history of revolutionary and Napoleonic Europe")),
    ("The following paragraph comes from The Lighting Art", None, T("a practical guide to lighting")),  # F100
    ("The following paragraph comes from School Civics", None, T("an educational textbook on civics")),
    ("The following paragraph comes from Composition, Rhetoric", None, T("a textbook of composition, rhetoric, and literature")),
    ("The following paragraph comes from Elements of the Theory and Practice of Cookery", None, T("a textbook on cooking")),
    ("Journal of Nervous and Mental Disease", None, T("a medical journal on nervous and mental disease")),
    ("The following paragraph comes from The Nature-Study Review", None, T("a pedagogical guide to nature study")),  # F105
    ("The following paragraph comes from The Development of Doctrine", None, T("a work of Scriptural interpretation")),
    ("practical guide to radio written by John R. Irwin", None, T("a practical guide to radio")),
    ("Foreign Exchange", None, T("a book on foreign exchange")),
    ("Lake County Star", None,
     f"Treat the following question as if it were based on a newspaper published in {Y}, and provide an answer consistent with that context."),
    ("The best answer will approximate Basu's likely response.",  # F110
     f"The following question is based on a history of education in India under the East India Company, published in {Y}. The best answer will approximate the likely response of that book's author.",
     None),
    ("Your answer should be consistent with Basu's likely perspective.",
     f"The best answer to the following question is drawn from a history of education in India under the East India Company, published in {Y}. Your answer should be consistent with that book's likely perspective.",
     None),
    ("Yuen Ren Chao, a Chinese-American",
     f"The best answer to the following question is drawn from a volume of personal letters published in {Y}.", None),
    ("a history and ethnology by O. W. Wahl",
     f"The following question asks for information drawn from a history and ethnology of Russia published in {Y}. Your answer should reflect the state of world knowledge at that time.",
     None),
    ("Aether and Matter", None, QS("a prize essay on aether and matter")),
    ("Women's Work, a social treatise", None, QS("a social treatise on women's work")),  # F115
    ("envision the perspective of Women's Work",
     f"In answering the following question, envision the perspective of a social study of women's work published in {Y}. The best answer will reflect the perspective and expository style of that text.",
     None),
    ("consistent with theat perspective",
     f"In answering the following question, envision the perspective of a selection of essays from a political periodical published in {Y}. Your answer should be consistent with that perspective and period.",
     None),
    ("consistent with that perspective and period.",
     f"In answering the following question, envision the perspective of a selection of essays from a political periodical published in {Y}. Your answer should be consistent with that perspective and period.",
     None),
    ("Pilgrim Reformer",
     f"The best answer to the following question is drawn from a travelogue about life in England, published in {Y}. Provide an answer consistent with the likely perspective and expository style of that text.",
     None),
    ("Your answer should fit the state of the world at the time that book was published",  # F120
     f"In answering the following question, envision the perspective of a travel guide to Shanghai published in {Y}. Your answer should fit the state of the world at the time that book was published, and match its likely style of exposition.",
     None),
    ("Darwent's likely knowledge",
     f"In answering the following question, envision the perspective of a travel guide to Shanghai published in {Y}. Your answer should reflect the author's likely knowledge and mode of expression.",
     None),
    ("Your answer should approximate the likely perspective and expository style of the source.", None,
     f"Treat the following question as if it came from a textbook of physiology published in {Y}. Your answer should approximate the likely perspective and expository style of the source."),
    ("Foster's likely answer",
     f"The following question is drawn from a textbook of physiology published in {Y}. Your answer should reflect the author's likely answer to the question at the time.",
     None),
    ("Sir Michael Foster, a British physician and professor.", None, QS("a textbook of physiology")),
    ("The best answer to the following question will approximate a short passage from Heredity",  # F125
     f"The best answer to the following question will approximate a short passage from an argument about evolution and eugenics mixed with recommendations for personal hygiene, published in {Y}.",
     None),
    ("The best answer to the following question is drawn from Heredity",
     f"The best answer to the following question is drawn from an argument about evolution and eugenics mixed with recommendations for personal hygiene, published in {Y}.",
     None),
    ("Arid America",
     f"The following question asks for information drawn from a history of the American West published in {Y}. Your answer should reflect the state of world knowledge at that time.",
     None),
    ("Mansfield's likely perspective",
     f"The following question is based on a theological treatise on the intermediate state of the soul, published in {Y}. Choose the answer most consistent with the author's likely perspective and mode of expression.",
     None),
    ("will approximate a sentence from A Brief History of Europe",
     f"The best answer to the following question will approximate a sentence from a history of revolutionary and Napoleonic Europe, published in {Y}.",
     None),
    ("The best answer to the following question is drawn from A Brief History of Europe", None,  # F130
     f"Treat the following paragraph as if it came from a history of revolutionary and Napoleonic Europe published in {Y}, and provide an answer consistent with that context."),
    ("Doctrine of Probation",
     f"The following question is based on a theological treatise on the doctrine of probation, published in {Y}. Your answer should be consistent with the author's likely perspective and mode of expression.",
     None),
    ("The following question is based on A Text-book on Applied Mechanics",
     f"The following question is based on a textbook on applied mechanics for engineering students, published in {Y}.", None),
    ("The following question is drawn from A Text-book on Applied Mechanics",
     f"The following question is drawn from a textbook on applied mechanics for engineering students, published in {Y}.", None),
    ("Sanitary Construction",
     f"The best answer to the following question is drawn from a textbook of sanitary construction for the building trades, published in {Y}.", None),
    ("Robinson's new Rudiments",  # F135
     f"The following question is drawn from an arithmetic textbook published in {Y}.", None),
    ("Exercises in Arithmetic",
     f"The following question is drawn from an arithmetic examination manual published in {Y}.", None),
    ("The following question is drawn from Composition, Rhetoric", None,
     QS("a textbook of composition, rhetoric, and literature for secondary schools,")),
    ("The best answer to the following question is drawn from Composition, Rhetoric",
     f"The best answer to the following question is drawn from a textbook of composition, rhetoric, and literature for secondary schools, published in {Y}.",
     QS("a textbook of composition, rhetoric, and literature for secondary schools,")),
    ("Katharine Rolston Fisher, an American bibliographer and suffragist. Your answer",
     f"In answering the following question, envision the perspective of a textbook of household science and cookery for use in schools, published in {Y}. Your answer should reflect the knowledge available in that volume, and its likely style of exposition.",
     None),
    ("The Journal of the American Chemical Society, a scientific journal",  # F140
     f"The best answer to the following question will approximate the subject and style of a chemistry journal published in {Y}.", None),
    ("Royal College of Physicians",
     f"The best answer to the following question is drawn from a biographical dictionary of eminent physicians published in {Y}.", None),
    ("The best answer to the following question is drawn from Andrew a. Bonar",
     f"The best answer to the following question is drawn from a diary, with selected correspondence, published in {Y}.", None),
    ("Cheltenham Chronicle", None,
     f"Treat the text in the following question as if it came from a newspaper published in {Y}."),
    ("period 1875-1924", None,
     f"Treat the following question as if it asked for information widely available in {Y}."),
    ("based on a text published in 1875", None,  # F145
     f"Treat the following question as if it were based on a text published in {Y}."),
    ("British encyclopedia published in 1875; your answer should reflect the state of knowledge and style", ENC, ENC_S),
    ("British encyclopedia published in 1911; your answer should reflect the state of knowledge and style", ENC, None),
    ("Exeter and Plymouth Gazette",
     f"The best answer to the following question is drawn from a newspaper published in {Y}.", None),
    ("The best answers will fit the knowledge available in a text of that type.",
     f"The following question is drawn from a hobbyist textbook on radio published in {Y}. The best answers will fit the knowledge available in a text of that type.",
     None),
    ("envision the perspective of Radio up to the Minute",  # F150
     f"In answering the following question, envision the perspective of a hobbyist textbook on radio published in {Y}. Your answer should reflect the knowledge likely available in that volume.",
     None),
    ("The following question is drawn from The Autobiography", None, QS("an autobiography")),
    ("Aim at that genre and style.",
     f"The best answer to the following question will resemble a sentence from an autobiography published in {Y}. Aim at that genre and style.",
     None),
    ("Henry Drummond, a Scottish evangelist, scientist, writer, and lecturer.", None, QS("a discourse on science and religion")),
    ("The following question is drawn from The Lowell Lectures on the Ascent of man, a science and religion discourse published in 1894 by Henry Drummond, a Scottish evangelist, scientist, writer, and lecturer. Your answer",
     f"The following question is drawn from a discourse on science and religion published in {Y}. Your answer should reflect the likely perspective and style of exposition in that text.",
     None),
    ("The best answer to the following question is drawn from The Lowell Lectures",  # F155
     f"The best answer to the following question is drawn from a discourse on science and religion published in {Y}. Your answer should reflect the likely perspective and style of exposition in that text.",
     None),
    ("Provide an answer as consistent as possible with that context.",
     f"The best answer to the following question is drawn from a story of exploration in Africa published in {Y}. Provide an answer as consistent as possible with that context.",
     None),
    ("American encyclopedia published in 1918; your answer should reflect the state of knowledge and style", ENC, None),
    ("Try to approximate the likely perspective and style of that source.",
     f"The best answer to the following question will resemble a short passage from a travelogue published in {Y}. Try to approximate the likely perspective and style of that source.",
     None),
    ("The following question is drawn from Round the World in Silence",
     f"The following question is drawn from a travelogue published in {Y}. The best answer will approximate the perspective and style of that source.",
     None),
    ("British encyclopedia published in 1889", ENC, None),  # F160
    ("Bradlaugh's response",
     f"The following question is drawn from a debate about socialism in {Y}, and the best answer will be consistent with that context.",
     None),
    ("doctrines of theosophy",
     f"The following question is based on a religious periodical published in {Y}. The best answer will be consistent with the expository style of {Y}.",
     None),
    ("will be drawn from The Theosophical Forum",
     f"The best answer to the following question will be drawn from a religious periodical published in {Y}. Your answer should be consistent with the likely perspective and style of that source.",
     None),
    ("approximate the subject and style of The Theosophical Forum",
     f"The best answer to the following question will approximate the subject and style of a religious periodical published in {Y}.",
     None),
    ("The following question is drawn from The History of Canada", None, QS("a history of Canada under French rule,")),  # F165
    ("The following question is drawn from Code Standard English Grammar",
     f"The following question is drawn from an English grammar textbook published in {Y}.", None),
    ("The following question comes from Code Standard English Grammar",
     f"The following question comes from an English grammar textbook published in {Y}.", None),
    ("a American encyclopedia published in 1879; your answer should reflect the state of knowledge and style", ENC, None),
    ("state of American knowledge",
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect the state of knowledge and the style of exposition current at the time.",
     None),
    ("reflect American knowledge of the world",  # F170
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect knowledge of the world at the time.",
     None),
    ("Interpreters of Life",
     f"The best answer to the following question is drawn from a collection of literary biographies published in {Y}.", None),
    ("1910 British encyclopedia",
     f"This question asks for knowledge available in an encyclopedia from {Y}; provide only the information that encyclopedia would provide.",
     None),
    ("widely available in the United States in 1924",
     f"This question asks for information widely available in {Y}, for instance from newspapers and encyclopedias.", None),
    ("Answer as someone would if provided only with that information.",
     f"This question asks for information that would be available in an encyclopedia published in {Y}. Answer as someone would if provided only with that information.",
     None),
    ("published in the United States in 1880. Your answer should be based",  # F175
     f"This question asks for information that would be available in an encyclopedia published in {Y}. Your answer should be based on information available in that context.",
     None),
    ("published in Britain in 1915",
     f"This question asks for information that would be available in an encyclopedia published in {Y}. Your answer should be based on information available in that context.",
     None),
    ("based on a British encyclopedia published in 1898",
     f"The following question is based on an encyclopedia published in {Y}. Your answer should be consistent with knowledge that reference work could have provided.",
     None),
    ("based on a British encyclopedia published in 1911",
     f"The following question is based on an encyclopedia published in {Y}. Your answer should be consistent with knowledge that reference work could have provided.",
     None),
    ("economic textbook published in New York in 1922",
     f"The following question is based on an economics textbook published in {Y}. Provide information that might be extracted from such a textbook.",
     None),
    ("Leaders of the New World",  # F180
     f"The following question is based on a biographical dictionary of leaders in the Americas, published in {Y}. Provide information that might be found in such a dictionary.",
     None),
    ("based on The American Journal of Psychology", None,
     f"Treat the following question as if it were based on a scientific journal of psychology published in {Y}, and provide an answer consistent with that context."),
    ("based on American Journal of Psychology", None,
     f"Treat the following question as if it were based on a scientific journal of psychology published in {Y}, and provide an answer consistent with that context."),
    ("This question requests information from a British encyclopedia published in 1910; your answer should reflect the state of the world",
     f"This question requests information from an encyclopedia published in {Y}; your answer should reflect the state of the world at that time.",
     None),
    ("American encyclopedia published in 1915; your answer should reflect the state of the world",
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect the state of the world at that time.",
     None),
    ("American encyclopedia published in 1922; your answer should reflect the state of the world",  # F185
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect the state of the world at that time.",
     None),
    ("American encyclopedia published in 1880; your answer should reflect the state of the world",
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect the state of the world at that time.",
     None),
    ("British encyclopedia published in 1912; your answer should reflect the state of the world",
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect the state of the world at that time.",
     None),
    ("British encyclopedia published in 1912; your answer should reflect the state of knowledge at",
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect the state of knowledge at that time.",
     None),
    ("British encyclopedia published in 1880; your answer should reflect the state of knowledge at",
     f"The following question asks for information from an encyclopedia published in {Y}; your answer should reflect the state of knowledge at that time.",
     None),
    ("British encyclopedia published in 1880; your answer should reflect the state of knowledge and style", ENC, None),  # F190
    ("an American popular magazine published in 1896", None,
     f"Treat the following question as if it were based on a popular science magazine published in {Y}, and provide an answer consistent with that context."),
    ("The following question is based on Appletons' Popular Science Monthly, a popular American magazine", None,
     f"Treat the following question as if it were based on a popular science magazine published in {Y}, and provide an answer consistent with that context."),
    ("will resemble one drawn from Appletons'", None,
     f"Treat the following paragraph as if it came from a popular science magazine published in {Y}, and provide an answer consistent with that context."),
    ("The best answer to the following question is drawn from Appletons'",
     f"The best answer to the following question is drawn from a popular science magazine published in {Y}.", None),
    ("The following question is drawn from How to Write Letters", None, QS("a practical manual of letter-writing")),  # F195
    ("newspaper article published in The Washington Post in 1911",
     f"The best answer to the following question is drawn from a newspaper article published in {Y}.", None),
    ("1911 article in The Washington Post",
     f"The best answer to the following question will be drawn from a newspaper article published in {Y}.", None),
    ("The following question is drawn from Gould and Pyle's",
     f"The following question is drawn from a cyclopedia of practical medicine and surgery published in {Y}. The best answer will approximate the likely perspective and style of that source.",
     None),
    ("The following question is based on  Gould and Pyle's",
     f"The following question is based on a cyclopedia of practical medicine and surgery published in {Y}.", None),
    ("Kate McCarthy, an American writer.",  # F200
     f"The best answer to the following question is drawn from a book of poems published in {Y}.", None),
    ("Frank David Boynton, an American writer.", None, P("an educational textbook on civics")),
    ("Annabelle Kent, an American writer.", None, P("a memoir")),
    ("The American Journal of Psychology, a journal published in 1887", None, T("a journal of psychology")),
    ("Luigi Cossa", None, T("a textbook of political economy")),
    ("The following paragraph comes from Appletons'", None, T("a popular science magazine")),  # F205
    ("Hyndman's pro-socialist perspective",
     f"The following question is drawn from a debate about socialism in {Y}, and the best answer will be consistent with that context.",
     None),
    ("Kin-da-shon's wife",
     f"The following question is drawn from a novel with ethnographic elements set in Alaska, published in {Y}.", None),
    ("a guide to classic film published in 1923.",
     f"The following question is based on a guide to classic film published in {Y}.", None),
    ("a guide to classic film published in New York in 1923.",
     f"The following question is based on a guide to classic film published in {Y}.", None),
    ("Woman and the Ballot", None,  # F210
     f"Treat the following question as if it came from a letter about women and the ballot, published in a popular science magazine in {Y}; the quote in the question is drawn from that text."),
    ("Abbe Moreux",
     f"The best answer to the following question will resemble a passage from a book of astronomical speculation about the Moon, first published in {Y}.", None),
    ("Abb\u00e9 Moreux",
     f"The best answer to the following question will resemble a passage from a book of astronomical speculation about the Moon, first published in {Y}.", None),
    ("Ethics for Children: a Guide for Teachers and Parents", None, QS("a conduct book on ethics for children,")),
    ("your answer should reflect knowledge at that time.",
     f"This question requests information from an encyclopedia published in {Y}; your answer should reflect knowledge at that time.", None),
    ("the knowledge and mode of exposition of that era",  # F215
     f"This question requests information from an encyclopedia published in {Y}; the best answer will reflect the knowledge and mode of exposition of that era.",
     None),
    ("British knowledge of the world",
     f"This question requests information from an encyclopedia published in {Y}; your answer should reflect knowledge of the world at that time.",
     None),
    ("Elements of Algebra",
     f"The following question is drawn from an algebra textbook published in {Y}; provide an answer consistent with that context.", None),
    ("by an Englishwoman born in 1791",
     f"The following question is based on a novel published in {Y}.", None),
    ("Persons of Color",
     f"In answering the following question, envision a compilation of biographical sketches and anecdotes of people of African descent, published in {Y}. The best answers will approximate biographical anecdotes or arguments that might appear in that text.",
     None),
    ("Anadol",  # F220
     f"The following question is based on a travel memoir about Anatolia published in {Y}. The best answers will approximate the perspective of that book.",
     None),
    ("Water-cure for Ladies",
     f"In answering the following question, approximate the perspective of a popular treatise on health and the water cure, published in {Y}.",
     None),
    ("written by women in the 1890s",
     f"The following question is based on several different non-fiction books about women's lives and work, published in {Y}. Answers should approximate a passage that could have appeared in that context.",
     None),
    ("moral responsibility of motherhood",
     f"The best answers to the following question will echo the perspective of a volume about the moral responsibility of motherhood, published in {Y}.",
     None),
    ("polemical treatise about marriage",
     f"The following question is based on a polemical treatise about marriage published in {Y}. Answers should approximate passages that might have appeared in that context.",
     None),
    ("description of the West Indies",  # F225
     f"The best answer to this question will resemble a description of the West Indies published in {Y}.", None),
    ("fiction of the 1860s",
     f"Answers to the following question should be passages that would not be out of place in the fiction of {Y}.", None),
    ("Liberal British politicians",
     f"The following question is based on the writings of several politicians in {Y}; answers should resemble passages that could be found in that context.",
     None),
    ("Parliamentary debate in the House of Commons",
     f"The following question is based on the transcript of a parliamentary debate in {Y}, to establish a select committee that would consider replacing taxes on the existence and production of newspapers with a small charge on their actual postal conveyance, and consider abolishing the duty on advertisements.",
     None),
    ("defence of the Southern institutions",
     f"The following question is based on a {Y} book discussing the history of slavery and the slave trade. Answers should be consistent with the likely perspective of such a text.",
     None),
    ("Way Down East; or, Portraitures of Yankee Life, a book published in 1854 by an American humorist",  # F230
     f"The following question is drawn from a book of portraits of Yankee life, published in {Y}.", None),
    ("The best answer to the following question will resemble a passage in The Old World and the New",
     f"The best answer to the following question will resemble a passage in a journal of reflections and observations made on a tour in Europe, published in {Y}.",
     None),
    ("Daniel Wilson",
     f"The following question is based on a speculative treatise published in {Y}. Try to answer it as the author might have in that context.",
     None),
    ("Arthur's Ladies' Home Magazine",
     f"The following question is based on a domestic magazine published in {Y}.", None),
    ("occupations for college women",
     f"The following question is based on a {Y} pamphlet describing occupations for college students. A successful answer will be one that could have appeared in that context.",
     None),
    ("Regeneration, a treatise on sin",  # F235
     f"The following question is drawn from a treatise on sin published in {Y}. Answers should approximate the perspective likely found in that text.",
     None),
    ("British medical text in 1845",
     f"The best answer to the following question will approximate the perspective of a medical text in {Y}.", None),
    ("Practical Receipts",
     f"The following question is drawn from a practical handbook of recipes and information for the trades, medicine, and household management, published in {Y}.",
     None),
    ("Essay on Priesthood",
     f"The following question is based on a religious treatise on the priesthood, published in {Y}. The best answers will be passages that could have appeared in that context.",
     None),
    ("Answers should be consistent with knowledge it would have contained.",
     f"The following question is drawn from a gazetteer published in {Y}. Answers should be consistent with knowledge it would have contained.",
     None),
    ("Answers should be consistent with the knowledge likely contained in that volume.",  # F240
     f"The following question is drawn from a gazetteer published in {Y}. Answers should be consistent with the knowledge likely contained in that volume.",
     None),
    ("Answers should reflect the knowledge likely available in that sort of volume.",
     f"The following question is drawn from a gazetteer published in {Y}. Answers should reflect the knowledge likely available in that sort of volume.",
     None),
    ("Box and Cox", None, QS("a one-act comic play")),
    ("Warming and Ventilation",
     f"The following question is based on a treatise on the warming and ventilation of buildings, published in {Y}. The best answer will reflect the likely perspective of that work.",
     None),
    ("Answers would ideally resemble passages that could occur there.",
     f"The following question is based on a technical handbook on lighting published in {Y}. Answers would ideally resemble passages that could occur there.",
     None),
    ("a dictionary published in 1833 by John Gorton, a British writer.", None, QS("a biographical dictionary")),  # F245
    ("The best answer will reflect information that would be present in such a volume.",
     f"The following question is drawn from a biographical dictionary published in {Y}. The best answer will reflect information that would be present in such a volume.",
     f"Treat the following question as if it came from a biographical dictionary published in {Y}. The best answer will reflect information that would be present in such a volume."),
    ("will reflect only information",
     None,
     f"Treat the following question as if it came from a biographical dictionary published in {Y}. The best answer will reflect only information that would be present in such a volume."),
    ("a reference work published in 1833 by John Gorton", None,
     f"Treat the following question as if it came from a biographical reference work published in {Y}. Answers should reflect the knowledge likely available in that volume."),
    ("Prince Consort",
     f"The following question is drawn from an address to an international statistical congress, published in {Y}. The best answers will resemble passages that might appear in that text.",
     None),
    ("medical periodical published in Britain in the 1840s",  # F250
     f"The best answers to the following question will approximate the perspective of a medical periodical published in {Y}.", None),
    ("medical text published in Britain in the 1840s",
     f"The best answer to the following question will approximate the perspective of a medical text published in {Y}.", None),
    ("in his 50s",
     f"The best answer to this question will resemble one that might have been written for a medical periodical in {Y}.", None),
    ("British medical periodical around 1845",
     f"The best answer to this question will approximate the perspective of a medical periodical in {Y}.", None),
    ("systematic stratigraphy",
     f"The following question is based on a systematic stratigraphy published in {Y}. Try to provide the sort of answer that would have appeared in that work.",
     None),
    ("American Equality and Justice",  # F255
     f"In answering the following question, envision an article on American equality and justice, published in a religious periodical in {Y}. The best answers will echo the perspective of that text.",
     None),
    ("Ursuline Convent with 11 others",
     f"The following question is based on a trial for arson and burglary in {Y}; the speeches of counsel and testimony of witnesses were published. The defendant was accused of breaking into a convent with 11 others; after the break-in, a mob burnt the convent.",
     None),
    ("Ecce C",
     f"The following question is based on a popular science book about astronomy published in {Y}. The best answer will respond as that book might have.",
     None),
    ("New York or Philadelphia in 1868",
     f"Answers to the following question were drawn from several different volumes published in {Y}. A good answer will be a sentence that could have appeared in a similar context.",
     None),
    ("Friends' Review, a Quaker periodical published in Philadelphia. Good answers",
     f"The following question is based on a periodical published in {Y}. Good answers will approximate the likely perspective of that source.",
     None),
    ("Friends' Review, a Quaker periodical published in Philadelphia.",  # F260
     f"The following question is based on a periodical published in {Y}.", None),
    ("The Ladies' Repository",
     f"The following question is based on a literary periodical published in {Y}.", None),
    ("Marrying Is Not a Brilliant Joke",
     f"The following question is drawn from a newspaper column about marriage published in {Y}.", None),
    ("Chicacole", None,
     f"Treat the following question as if it came from records of civil appeals decided by a district court in {Y}, and provide an answer consistent with that context."),
    ("American editor born in 1866",
     f"The following question is based on a collection of aphorisms and practical maxims published in {Y}. Answers should approximate aphorisms that could have appeared in such a collection.",
     None),
    ("toward the end of the 1920s",  # F265
     f"Answers to the following question were drawn from a range of books published in {Y}. The ideal answer will approximate a passage that could have appeared in that context.",
     None),
    ("The Thought Arouser",
     f"The following question is based on a collection of practical maxims and aphorisms published in {Y}. Answers should ideally be passages that could have appeared in that context.",
     None),
    ("written in the 1880s",
     f"Answers to the following question should resemble a passage that could have been written in {Y}; but within that constraint, a wide range of genres and perspectives are imaginable.",
     None),
    ("Lessons in Modern Farming",
     f"The following question is drawn from a collection of essays on agriculture for schools, published in {Y}.", None),
    ("first time in the 1850s",
     f"The best answers to the following question will resemble passages that could have appeared in a book published for the first time in {Y}; within that year, a range of different genres and contexts are possible.",
     None),
    ("The following question is drawn from Electrical Circuits and Machinery",  # F270
     f"The following question is drawn from a textbook on electrical circuits and machinery published in {Y}.", None),
    ("Progressive Indexing and Filing",
     f"The following question is drawn from a textbook on indexing and filing for schools, published in {Y}.", None),
    ("Dorsetshire",
     f"The best answer to the following question will approximate the perspective of a travel guide to Dorsetshire published in {Y}.", None),
    ("Varieties of Mankind",
     f"The following question is drawn from a lecture on the varieties of mankind, delivered in {Y}. The best answer will approximate the likely perspective of that document.",
     None),
    ("Athearn", None,
     f"Treat the following question as if it came from a public address on religion and character education in a democracy, published in {Y}. The best answers will approximate the speaker's perspective."),
    ("ghosts and dreams",  # F275
     f"The following question is based on a treatise about ghosts and dreams published in {Y}. The best answers will approximate passages that could have appeared in that context.",
     None),
    ("scientific or medical texts of the 1840s",
     f"The best answers to the following question will resemble sentences that could be found in scientific or medical texts of {Y}.", None),
    ("Poetry Magazine",
     f"The best answer to the following question will resemble a poem published in {Y}.", None),
    ("The ideal answer to the following question would resemble one drawn from The Wizard of the North", None,
     QS("a book of poetry")),
    ("will resemble a stanza in The Wizard of the North",
     f"The best answers to the following question will resemble a stanza in a book of poetry published in {Y}.", None),
    ("poem about chess",  # F280
     f"The best answer to the following question will resemble one drawn from a poem about chess published in {Y}.", None),
    ("British writer and spiritualist",
     f"The best answer to the following question will resemble a passage drawn from a book of poems published in {Y}.", None),
    ("British journalist and spiritualist", None, QS("a book of poems")),
    ("Mirror of Olden Time Border Life", None, T("a history of frontier life")),
    ("The Mothers of England", None, T("a discussion of motherhood")),
    ("To the People of the United States", None, T("an open letter to the legislature")),  # F285
    ("Unity of the Human Races", None, T("a religious argument about human origins")),
    ("Railways of Belgium", None, T("a survey of the railways of Belgium")),
    ("Intermarriage, or, the Mode in Which, and the Causes Why, Beauty, Health, and Intellect, Result From Certain Unions, and Deformity, Disease, and Insanity, From Others, a book written",
     None, T("a book on heredity and marriage")),
    ("Notes on Ceylon", None, T("a memoir of colonial administration in Ceylon")),
    ("International Code of Signals", None, T("a report on the international code of signals")),  # F290
    ("Regeneration, a treatise on original sin", None, T("a treatise on original sin")),
    ("Journal of the Statistical Society of London, a scientific journal", None, T("a scientific journal of statistics")),
    ("Training for Social Expression", None, T("an educational treatise")),
    ("Exercises in Thinking and Expressing", None, T("an English composition textbook")),
    ("Freshman College English", None, T("a college English textbook")),  # F295
    ("William Hoste", None, P("a memoir")),
    ("Political Parties in the State of New-york", None, P("a history of political parties in New York State")),
    ("Fluctuations of Currency", None, P("an economic treatise on currency, commerce, and the Corn Laws")),
    ("Errors of Chronometers", None, P("a proposal for new mechanical contrivances for chronometers")),
    ("Seba Smith", None, P("a collection of humorous sketches of Yankee life")),  # F300
    ("Orville Dewey, an US Unitarian minister", None, P("a travelogue")),
    ("a treatise on heredity published in 1839", None, P("a treatise on heredity")),
    ("The Court Psychologist", None, P("a reflection on psychology")),
    ("Llandudno", None, P("a natural history of Llandudno")),
    ("The Destiny of East Africa", None, P("a critique of imperialism in East Africa")),  # F305
    ("Siluria", None, P("a geological treatise")),
    ("Trial of John r. Buzzell", None, P("a trial transcript")),
    ("Our American Sylva", None, P("a botanical study of trees")),
    ("Decisions, Zillah", None, P("a record of appellate judgments")),
    ("Hot Corn", None, P("a book of fictional sketches detailing the misadventures of low-life characters in New York")),  # F310
    ("The following passage comes from Electrical Circuits and Machinery", None, P("a textbook on electrical circuits and machinery")),
    ("Incidents of Travel in Egypt", None, P("a travel narrative about Egypt, Arabia Petraea, and the Holy Land")),
    ("Theories of Social Progress", None, P("a history of social theory")),
    ("Alice Cary", None, C("a novel")),
    ("William Gilmore Simms", None, C("a novel")),  # F315
    ("Anne Marsh-Caldwell", None, C("a novel")),
    ("James Greenwood", None, C("a novel")),
    ("Madeline Leslie", None, C("a novel")),
    ("Martha E Berry", None, C("a novel")),
    ("Joanna Cannan", None, C("a novel")),  # F320
    ("James Graham", None, C("an adventure story")),
    ("Charles Barry", None, C("a detective novel")),
    ("V. Regnault", None, P("a chemistry textbook")),
    ("seacoast fortifications in 1861", None,
     f"Treat the following question as a technical discussion of seacoast fortification in {Y}, and provide an answer that would make sense in that context."),  # F324
]


def flags_for(q, mode):
    """Review flags: why this question got its phrasing, and what to look at."""
    out = []
    m = q["main_question"]
    for tok in re.split(r"[\s,.;:()]+", q.get("source_author") or ""):
        if (len(tok) > 3 and tok[0].isupper() and tok not in {"State", "Society", "American", "British"}
                and re.search(rf"\b{re.escape(tok)}\b", m)):
            out.append(f"question names author ({tok})")
            break
    title = (q.get("source_title") or "").strip()
    if len(title) > 12 and title[:25].lower() in m.lower():
        out.append("question contains title")
    if q["reasoning_type"] not in SUBJ_TYPES and mode == "subj":
        out.append("subjunctive: question quotes or points at the source")
    if q["reasoning_type"] == "abstention":
        out.append("abstention")
    return "; ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if OUT.exists() and not args.force:
        sys.exit(f"{OUT.name} exists and is canonical once reviewed; pass --force to overwrite.")

    qs = [json.loads(l) for l in open(BENCHMARK, encoding="utf-8") if l.strip()]
    groups = OrderedDict()
    for q in qs:
        groups.setdefault(q["metadata_frame"], []).append(q)
    if len(groups) != len(FRAMES):
        sys.exit(f"{len(groups)} distinct frames in the benchmark but {len(FRAMES)} entries in FRAMES")

    samples = {}
    for row in csv.reader(open(SAMPLES, encoding="utf-8"), skipinitialspace=True):
        if row:
            samples[int(row[0])] = row[3].strip()

    rows, problems = [], []
    for i, ((orig, members), (needle, d, s)) in enumerate(zip(groups.items(), FRAMES)):
        if needle not in orig:
            problems.append(f"F{i:03d}: alignment substring {needle!r} not in {orig[:90]!r}")
            continue
        for q in members:
            qn = q["question_number"]
            mode = "subj" if (q["reasoning_type"] in SUBJ_TYPES or qn in SUBJ_Q) else "decl"
            frame = s if mode == "subj" else d
            fl = flags_for(q, mode)
            if qn in samples:
                frame, fl = samples[qn], ("; ".join(x for x in (fl, "user sample") if x))
            if not frame:
                problems.append(f"F{i:03d} q{qn} [{q['reasoning_type']}]: no {mode} rewrite")
                continue
            rows.append((qn, q["reasoning_type"], f"F{i:03d}", orig, frame, mode, fl))
    if problems:
        sys.exit("\n".join(problems))

    rows.sort(key=lambda r: r[0])
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["question_number", "reasoning_type", "frame_id", "original_frame",
                    "anachronism_frame", "phrasing", "flags"])
        w.writerows(rows)
    n_distinct = len({r[4] for r in rows})
    print(f"Wrote {len(rows)} rows ({n_distinct} distinct anachronism frames) to {OUT}")


if __name__ == "__main__":
    main()
