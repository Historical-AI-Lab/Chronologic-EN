# Anachronism pilot — GPT-5.4 (medium), 40 questions, 2026-11-26

Answers: `modelasjudge/generated_answers/free_gen_gpt-5.4-anachronismpilot__1.0.json`
(benchmark `chronologic_anachronism_pilot_1.0.jsonl`; sha256 in
`benchmark_sha256.txt`). Each answer is compared with GPT-5.4's original
answer to the same question under the true frame:
`GPT-1914/chronologic/modelasjudge/generated_answers/free_gen_gpt-5.4__0.7.json`.
The question text and true frame match 1.0 for all 40. Unscored; this is a
qualitative read.

## Verdict: the frames work as intended; no wording changes needed

- **No demurrals.** No answer refuses, flags an anachronism, or comments on
  the frame. A regex scan for meta-commentary ("as an AI", "this passage
  appears…", 2023, "historical", …) finds only two hits, and both are
  content (q675 "In nineteenth-century Britain…", q756 "modern
  neuroscience").
- **No change in length** (mean 21.8 words vs. 22.4 originally), and no
  question had its reasoning effort downgraded.
- **The model follows the 2023 frame wherever the question leaves it room.**
  The shift shows up in knowledge, register and attitude, not just
  vocabulary.

## What moved

| Type | Clear shift | Mild | Essentially unchanged |
|---|---|---|---|
| abstention | 606, 696, 697, 701 | | 750 |
| constrained_generation | 529, 756, 772 | 549 | 762 |
| knowledge | 544, 742 | | 7, 503, 505 |
| sentence_cloze | 201, 819, 821 | 812 | 838 |
| phrase_cloze | 333, 343 | 165 | 152, 407 |
| topic_sentence | 621, 675 | | 418, 448, 488 |
| character_modeling | 103 | | 52, 73, 91, 114 |
| inference | | 455, 469 | 428, 450, 482 |
| **total** | **17** | **5** | **18** |

Representative shifts (original → anachronism):

- **q696** (abstention; true answer under the 1924 frame is Campbell's Soup):
  "insufficient information" → "best known for popularizing the 'hero's
  journey' in comparative mythology."
- **q697, q701, q606:** "insufficient information" → a direct modern answer
  (League of Nations after WWI; *Another Thin Man*; the Indus). As expected,
  abstention fails almost automatically.
- **q756** (phrenology, true frame 1840s medical periodical): a cautious
  period critique → "provides essentially no valid … knowledge … repeatedly
  disproven by modern neuroscience."
- **q621** (Popular Science Monthly, 1896): "natural division of labor which
  springs from differences of constitution" → "Some evolutionary
  psychologists argue…"
- **q343** (1876 embryology): "to render this parallelism … more apparent to
  the student" → "illuminate deuterostome body-plan evolution."
- **q819** (1854 Yankee humor): "no more damaged than a pumpkin after a hard
  frost" → "booked for a flat obituary and a church basement casserole."
- **q544** (1902 journalist's fee): "one guinea" → "two hundred pounds."
- **q742** (1847 gazetteer, "the chief and only port of Japan"):
  "Nagasaki" → "insufficient information." No single port answers this in
  2023, so this is frame-following, not error.
- **q529, q772, q333, q201, q103, q821:** modern encyclopedia, sales-advice,
  engineering, regulatory and thriller registers respectively.

## What didn't move, and why that's fine

- **Strong period text in the question anchors the answer.** Character
  modeling quotes period descriptions of the character, and its dialogue
  stayed archaic in 4 of 5 cases (q103, a spy story, moved). The same holds
  for the convent-arson trial (q762, q838), Scripture (q418), and the
  quoted biographical entry (q750). "Treat as if" / "Suppose" does not
  override the question's own evidence. That is the trade-off you chose to
  keep results comparable with the original runs, and it means the
  ablation's effect is a lower bound for these types.
- **q503** ("Date this text") still answers 1899. The model sensibly dates
  the quoted text rather than the frame.
- **Arithmetic and mechanics are frame-insensitive**, apart from notation
  (q469 "$0.09 per pint"; q455 answers in module units "m" instead of
  fractions of pitch). Differences on q7 and q428 look like ordinary
  run-to-run noise; both answers were wrong in both conditions on q7.

## Implications for the full runs

- Expect the largest drops in **abstention** (near-automatic) and
  **constrained generation**, then cloze. Character modeling and inference
  should move least.
- The style channel should register strongly. Many shifted answers are
  modern in register even where the substance is defensible.
