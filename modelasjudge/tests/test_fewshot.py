"""Tests for few-shot exemplar selection, rendering, and pipeline threading.

A whitespace word count stands in for Talkie's tokenizer, so these run
without tiktoken or the Talkie vocab.
"""

import json
import random
from argparse import Namespace
from pathlib import Path

import pytest

import fewshot
import free_generation as fg
from run_pipeline import effective_candidate_label

SAMPLE = Path(__file__).resolve().parents[2] / "booksample" / "chronologic_en_1.0_sample.jsonl"
NTOK = lambda s: len(s.split())  # noqa: E731


def q(n, rt, src, author="", question=None, gt="An answer.", frame="A frame."):
    return {
        "question_number": n, "reasoning_type": rt, "source_htid": src, "source_author": author,
        "main_question": question or f"Unique question number {n} about topic {n * 7919}?",
        "metadata_frame": frame, "question_category": rt,
        "answer_strings": [gt, "A distractor answer.", "Another distractor."],
        "answer_types": ["ground_truth", "manual", "manual"], "frame_type": "world_context",
    }


def world_qa_bench():
    qs, n = [], 0
    for rt in ("knowledge", "inference", "abstention"):
        for i in range(6):
            n += 1
            gt = "insufficient information" if rt == "abstention" and i < 4 else "A fact."
            qs.append(q(n, rt, f"src{n}", author=f"author{n}", gt=gt))
    return qs


def load_sample():
    return [json.loads(l) for l in SAMPLE.read_text(encoding="utf-8").splitlines() if l.strip()]


# --- selection --------------------------------------------------------------

def test_world_qa_gets_one_of_each_type_and_a_refusal():
    qs = world_qa_bench()
    by = {x["question_number"]: x for x in qs}
    m = fewshot.build_manifest(qs, 3, 0, NTOK)
    for e in m["entries"].values():
        assert sorted(e["exemplar_types"]) == ["abstention", "inference", "knowledge"]
        abst = [by[n] for n in e["exemplars"] if by[n]["reasoning_type"] == "abstention"]
        assert fewshot.is_refusal(abst[0])


def test_world_qa_type_order_varies():
    m = fewshot.build_manifest(world_qa_bench(), 3, 0, NTOK)
    positions = {tuple(e["exemplar_types"]).index("abstention") for e in m["entries"].values()}
    assert len(positions) > 1


@pytest.mark.parametrize("cand_kw", [
    {"src": "hvd.ABC123"},                      # same book, different ID spelling
    {"src": "other", "author": "Jane Doe"},     # same author
    {"src": "other", "question": "What is the current state of scientific opinion about the theories of Mr Darwin?"},
])
def test_eligibility_exclusions(cand_kw):
    t = q(1, "phrase_cloze", "abc123", author="Jane Doe",
          question="What is the current state of scientific opinion about the theories of Darwin?")
    kw = {"src": "x", "author": "", **cand_kw}
    c = q(2, "phrase_cloze", kw["src"], author=kw["author"], question=kw.get("question"))
    assert not fewshot.eligible(t, c)


def test_eligibility_allows_unrelated_and_respects_pools():
    t = q(1, "knowledge", "a", author="A")
    assert fewshot.eligible(t, q(2, "abstention", "b", author="B"))     # pooled
    assert not fewshot.eligible(t, q(3, "phrase_cloze", "b", author="B"))


def test_sample_manifest_invariants():
    qs = load_sample()
    by = {x["question_number"]: x for x in qs}
    m = fewshot.build_manifest(qs, 3, 0, NTOK)
    for qn, e in m["entries"].items():
        t = by[int(qn)]
        assert len(e["exemplars"]) == 3 and int(qn) not in e["exemplars"]
        for n in e["exemplars"]:
            assert fewshot.eligible(t, by[n])
        if e["pool"] == "world_qa":
            assert sorted(e["exemplar_types"]) == ["abstention", "inference", "knowledge"]


def test_selection_independent_of_file_order():
    qs = load_sample()
    shuffled = qs[:]
    random.Random(1).shuffle(shuffled)
    a = fewshot.build_manifest(qs, 3, 0, NTOK)["entries"]
    b = fewshot.build_manifest(shuffled, 3, 0, NTOK)["entries"]
    assert all(a[k]["exemplars"] == b[k]["exemplars"] for k in a)


def test_seed_changes_selection():
    qs = load_sample()
    a = fewshot.build_manifest(qs, 3, 0, NTOK)["entries"]
    b = fewshot.build_manifest(qs, 3, 1, NTOK)["entries"]
    assert sum(a[k]["exemplars"] != b[k]["exemplars"] for k in a) > len(a) / 2


def test_fallback_drops_last_sampled(monkeypatch):
    qs = load_sample()
    full = fewshot.build_manifest(qs, 3, 0, NTOK)["entries"]
    monkeypatch.setattr(fewshot, "CEILING", 600)
    tight = fewshot.build_manifest(qs, 3, 0, NTOK)["entries"]
    fell = [k for k, e in tight.items() if e["fallback"]]
    assert fell
    for k in fell:
        e = tight[k]
        assert e["exemplars"] + e["dropped"] == full[k]["exemplars"]
        assert e["projected_tokens"] <= 600 or e["k"] == 0


def test_k0_manifest_is_empty():
    m = fewshot.build_manifest(load_sample(), 0, 0, NTOK)
    assert all(e["exemplars"] == [] and not e["fallback"] for e in m["entries"].values())


# --- rendering --------------------------------------------------------------

def test_render_formats():
    qs = world_qa_bench()
    t, ex = qs[0], [qs[7], qs[13]]
    p = fewshot.render(t, ex)
    assert p.completion_text.endswith("ANSWER:")
    assert p.completion_text.count(fewshot.DELIM) == 3
    roles = [m["role"] for m in p.chat_messages()]
    assert roles == ["system", "user", "assistant", "user", "assistant", "user"]
    assert all("\nLENGTH: " in m["content"] for m in p.turns if m["role"] == "user")
    assert p.talkie_it_text().startswith("<|system|>") and p.talkie_it_text().endswith("<|assistant|>")
    assert p.max_tokens == fg.build_prompts(t)[2]           # same answer cap as zero-shot
    assert fewshot.FEWSHOT_NOTE in p.system
    assert "{length_spec}" not in p.system


def test_k0_render_has_no_examples_note():
    t = world_qa_bench()[0]
    p = fewshot.render(t, [])
    assert fewshot.FEWSHOT_NOTE not in p.system
    assert [m["role"] for m in p.chat_messages()] == ["system", "user"]


def test_system_prompt_choice_follows_zero_shot():
    assert fewshot.system_prompt(q(1, "knowledge", "a"), 3).startswith(fewshot.SYSTEM_PROMPT_A_FS)
    assert fewshot.system_prompt(q(1, "phrase_cloze", "a"), 3).startswith(fewshot.SYSTEM_PROMPT_B_FS)


def test_truncate_at_stops():
    assert fewshot.truncate_at_stops(" He went home.\n\n* * *\n\nCONTEXT: x") == " He went home.\n"
    assert fewshot.truncate_at_stops("Verse line one\nline two") == "Verse line one\nline two"


@pytest.mark.parametrize("requested,backend,tstyle,expected", [
    (None, "openai", None, "api_chat"),
    (None, "openrouter", None, "api_chat"),
    (None, "talkie", "it", "talkie_it"),
    (None, "talkie", "base", "completion"),
    ("chat", "hf", None, "hf_chat"),
    ("completion", "hf", None, "completion"),
])
def test_resolve_prompt_style(requested, backend, tstyle, expected):
    assert fewshot.resolve_prompt_style(requested, backend, tstyle) == expected


@pytest.mark.parametrize("requested,backend,tstyle", [
    (None, "hf", None), ("completion", "openai", None), ("chat", "talkie", "base")])
def test_resolve_prompt_style_errors(requested, backend, tstyle):
    with pytest.raises(ValueError):
        fewshot.resolve_prompt_style(requested, backend, tstyle)


# --- manifest IO and threading ---------------------------------------------

def test_load_or_build_roundtrip_and_validation(tmp_path):
    qs = load_sample()
    path = tmp_path / "m.json"
    m1, _ = fewshot.load_or_build_manifest(SAMPLE, qs, 3, 0, path, ntok=NTOK)
    m2, _ = fewshot.load_or_build_manifest(SAMPLE, qs, 3, 0, path, ntok=NTOK)
    assert m1["entries"] == m2["entries"]
    with pytest.raises(SystemExit):
        fewshot.load_or_build_manifest(SAMPLE, qs, 3, 1, path, ntok=NTOK)


def test_resume_refuses_prompt_format_mismatch(tmp_path):
    qs = load_sample()
    manifest = tmp_path / "m.json"
    fewshot.load_or_build_manifest(SAMPLE, qs, 3, 0, manifest, ntok=NTOK)
    out = tmp_path / "free_gen.json"
    out.write_text(json.dumps({"answers": {}, "reasoning_effort": "none"}))  # a zero-shot file
    with pytest.raises(SystemExit, match="fewshot"):
        fg.run_free_generation("qwen/qwen3-8b", str(SAMPLE), output_path=str(out),
                               fewshot_k=3, fewshot_manifest=str(manifest))


def test_effective_candidate_label():
    base = dict(candidate="openai/gpt-5.4", candidate_label=None)
    assert effective_candidate_label(Namespace(**base)) == "openai/gpt-5.4"
    assert effective_candidate_label(Namespace(**base, fewshot=None, fewshot_seed=0)) == "openai/gpt-5.4"
    assert effective_candidate_label(Namespace(**base, fewshot=3, fewshot_seed=0)) == "openai/gpt-5.4-fs3s0"
    lab = Namespace(candidate="x", candidate_label="talkie-base-fs0s1", fewshot=0, fewshot_seed=1)
    assert effective_candidate_label(lab) == "talkie-base-fs0s1"
