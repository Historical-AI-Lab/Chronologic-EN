"""Candidate-frame variants (anachronism, wrongframe): the builder, and the
guards that keep a variant run from sharing a label -- and so every output
file and ledger row -- with the real run of the same model."""

import importlib.util
import json
import sys
import types
from argparse import Namespace
from pathlib import Path

import pytest

import free_generation as fg
import naming
from run_pipeline import _FRAME_CONDITION_CACHE, effective_candidate_label

BUILDER_PATH = Path(__file__).resolve().parents[2] / "booksample" / "build_candidate_frame_variant.py"


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_candidate_frame_variant", BUILDER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(q, year=1897, author="Clarence Moores Weed", nat="American", rt="phrase_cloze",
         ft="passage_context", htid=None):
    return {
        "question_number": q, "reasoning_type": rt, "frame_type": ft,
        "source_htid": htid or f"h{q}", "source_author": author, "author_nationality": nat,
        "source_title": "The School Garden Book", "source_date": year,
        "metadata_frame": f"The following passage comes from The School Garden Book, "
                          f"published in {year} by {author}, an {nat} naturalist.",
        "substantive_metadata_frame": f"substantive {q}",
        "main_question": f"question {q}", "answer_strings": ["a", "b"],
        "answer_types": ["ground_truth", "x"],
    }


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def _write_frames(path, rows, header=("question_number", "anachronism_frame")):
    lines = ["\t".join(header)] + ["\t".join(map(str, r)) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


GOOD = "Treat the following passage as if it came from an educational guide published in 2025."


# ---------------------------------------------------------------------------
# naming helpers
# ---------------------------------------------------------------------------

def test_condition_of_plain_benchmark_is_none():
    assert naming.frame_condition_of_records([_rec(1), _rec(2)]) is None


def test_condition_detected():
    recs = [dict(_rec(q), candidate_metadata_frame=GOOD, candidate_frame_condition="anachronism")
            for q in (1, 2)]
    assert naming.frame_condition_of_records(recs) == "anachronism"


@pytest.mark.parametrize("recs", [
    [dict(_rec(1), candidate_metadata_frame=GOOD)],                         # unmarked override
    [dict(_rec(1), candidate_frame_condition="anachronism")],               # marker, no frame
    [dict(_rec(1), candidate_metadata_frame=GOOD, candidate_frame_condition="a"),
     dict(_rec(2), candidate_metadata_frame=GOOD, candidate_frame_condition="b")],  # mixed
    [dict(_rec(1), candidate_metadata_frame=GOOD, candidate_frame_condition="Bad-Name")],
])
def test_condition_refused(recs):
    with pytest.raises(naming.FrameConditionError):
        naming.frame_condition_of_records(recs)


def test_condition_label_suffix_added_once():
    assert naming.condition_label("gpt-5.4", "anachronism") == "gpt-5.4-anachronism"
    assert naming.condition_label("gpt-5.4-anachronism", "anachronism") == "gpt-5.4-anachronism"
    assert naming.condition_label("gpt-5.4", None) == "gpt-5.4"


def test_variant_name_keeps_version_but_is_never_latest(tmp_path):
    _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", [_rec(1)])
    variant = tmp_path / "chronologic_anachronism_1.0.jsonl"
    _write_jsonl(variant, [_rec(1)])
    assert naming.benchmark_version(variant) == "1.0"
    assert naming.latest_benchmark(tmp_path).name == "chronologic_en_1.0.jsonl"


# ---------------------------------------------------------------------------
# run_pipeline label
# ---------------------------------------------------------------------------

def test_pipeline_label_gets_condition_suffix(tmp_path):
    _FRAME_CONDITION_CACHE.clear()
    plain = _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", [_rec(1)])
    variant = _write_jsonl(tmp_path / "chronologic_anachronism_1.0.jsonl", [
        dict(_rec(1), candidate_metadata_frame=GOOD, candidate_frame_condition="anachronism")])
    base = dict(candidate="openai/gpt-4.1", candidate_label=None, fewshot=None, fewshot_seed=0)
    assert effective_candidate_label(Namespace(**base, benchmark=str(plain))) == "openai/gpt-4.1"
    assert (effective_candidate_label(Namespace(**base, benchmark=str(variant)))
            == "openai/gpt-4.1-anachronism")
    # An explicit label that already carries the suffix is not doubled.
    lab = dict(base, candidate_label="gpt-5.4-anachronism")
    assert effective_candidate_label(Namespace(**lab, benchmark=str(variant))) == "gpt-5.4-anachronism"


def test_pipeline_refuses_unmarked_variant(tmp_path):
    _FRAME_CONDITION_CACHE.clear()
    bad = _write_jsonl(tmp_path / "chronologic_en_1.0_old.jsonl",
                       [dict(_rec(1), candidate_metadata_frame=GOOD)])
    with pytest.raises(SystemExit):
        effective_candidate_label(Namespace(candidate="m", candidate_label=None, fewshot=None,
                                            fewshot_seed=0, benchmark=str(bad)))


# ---------------------------------------------------------------------------
# free_generation guards
# ---------------------------------------------------------------------------

VARIANT = [dict(_rec(q), candidate_metadata_frame=GOOD, candidate_frame_condition="anachronism")
           for q in (1, 2)]


def test_resolve_plain_benchmark_leaves_label():
    assert fg.resolve_frame_condition([_rec(1)], "gpt-5.4") == (None, "gpt-5.4")


def test_resolve_variant_suffixes_label():
    assert fg.resolve_frame_condition(VARIANT, "gpt-5.4") == ("anachronism", "gpt-5.4-anachronism")


def test_resolve_refuses_fewshot():
    with pytest.raises(SystemExit):
        fg.resolve_frame_condition(VARIANT, "gpt-5.4", fewshot_k=3)


def test_resolve_refuses_output_path_without_suffix(tmp_path):
    with pytest.raises(SystemExit):
        fg.resolve_frame_condition(VARIANT, "gpt-5.4", output_path=tmp_path / "free_gen_gpt-5.4__1.0.json")
    ok = tmp_path / "free_gen_gpt-5.4-anachronism__1.0.json"
    assert fg.resolve_frame_condition(VARIANT, "gpt-5.4", output_path=ok)[0] == "anachronism"


def test_resume_condition_mismatch_refused(tmp_path):
    fg.check_resume_condition({"candidate_frame_condition": "anachronism"}, "anachronism", "f")
    with pytest.raises(SystemExit):
        fg.check_resume_condition({}, "anachronism", "f")
    with pytest.raises(SystemExit):
        fg.check_resume_condition({"candidate_frame_condition": "anachronism"}, None, "f")


def test_run_free_generation_writes_suffixed_file(tmp_path, monkeypatch):
    """End to end with a stubbed backend: the variant run lands in its own file,
    records the condition, shows the candidate the variant frame, and keeps
    the true frame for the judge."""
    bench = _write_jsonl(tmp_path / "chronologic_anachronism_1.0.jsonl", VARIANT)
    seen = []

    def fake_generate(q, model_id, client, reasoning_effort="none"):
        seen.append(fg.build_prompts(q)[1])
        return "an answer", "spec"

    monkeypatch.setattr(fg, "is_openai_model", lambda m: True)
    monkeypatch.setattr(fg, "load_openai_credentials", lambda p: ("org", "key"))
    monkeypatch.setattr(fg, "generate_answer_openai", fake_generate)
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=lambda **kw: object()))

    out = fg.run_free_generation("gpt-5.4", str(bench), output_dir=str(tmp_path),
                                 candidate_label="gpt-5.4")
    out = Path(out)
    assert out.name == "free_gen_gpt-5.4-anachronism__1.0.json"
    data = json.loads(out.read_text())
    assert data["candidate_frame_condition"] == "anachronism"
    assert data["candidate_label"] == "gpt-5.4-anachronism"
    assert all(GOOD in p for p in seen)
    a = data["answers"]["1"]
    assert a["candidate_metadata_frame_used"] == GOOD
    assert a["metadata_frame"] == VARIANT[0]["metadata_frame"]


# ---------------------------------------------------------------------------
# builder
# ---------------------------------------------------------------------------

def test_builder_frames_mode(tmp_path, builder):
    recs = [_rec(1), _rec(2, year=1850)]
    inp = _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", recs)
    frames = _write_frames(tmp_path / "f.tsv", [(1, GOOD), (2, GOOD)])
    out = tmp_path / "chronologic_anachronism_1.0.jsonl"
    sha = tmp_path / "sha.txt"
    builder.main(["frames", "--input", str(inp), "--output", str(out), "--frames", str(frames),
                  "--require-year", "2025", "--sha-record", str(sha)])
    got = [json.loads(l) for l in out.read_text().splitlines()]
    assert [g["candidate_metadata_frame"] for g in got] == [GOOD, GOOD]
    assert all(g["candidate_frame_condition"] == "anachronism" for g in got)
    for g, r in zip(got, recs):
        assert {k: g[k] for k in r} == r
    assert builder.sha256_of(out) in sha.read_text()


@pytest.mark.parametrize("frame", [
    "An educational guide published in 1909.",            # wrong year
    "An educational guide published in 2025 or 1909.",    # extra year
    "",                                                   # empty
])
def test_builder_frames_mode_rejects_bad_frames(tmp_path, builder, frame):
    inp = _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", [_rec(1)])
    frames = _write_frames(tmp_path / "f.tsv", [(1, frame)])
    with pytest.raises(SystemExit):
        builder.main(["frames", "--input", str(inp), "--output", str(tmp_path / "v_1.0.jsonl"),
                      "--frames", str(frames), "--require-year", "2025"])


def test_builder_refuses_partial_coverage_unless_asked(tmp_path, builder):
    inp = _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", [_rec(1), _rec(2)])
    frames = _write_frames(tmp_path / "f.tsv", [(1, GOOD)])
    out = tmp_path / "pilot_1.0.jsonl"
    args = ["frames", "--input", str(inp), "--output", str(out), "--frames", str(frames)]
    with pytest.raises(SystemExit):
        builder.main(args)
    builder.main(args + ["--only-covered"])
    assert len(out.read_text().splitlines()) == 1


def test_builder_checks_original_frame_column(tmp_path, builder):
    inp = _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", [_rec(1)])
    frames = _write_frames(tmp_path / "f.tsv", [(1, "not the real frame", GOOD)],
                           header=("question_number", "original_frame", "anachronism_frame"))
    with pytest.raises(SystemExit):
        builder.main(["frames", "--input", str(inp), "--output", str(tmp_path / "v_1.0.jsonl"),
                      "--frames", str(frames)])


def test_builder_refuses_version_change_and_latest_name(tmp_path, builder):
    inp = _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", [_rec(1)])
    frames = _write_frames(tmp_path / "f.tsv", [(1, GOOD)])
    for name in ("chronologic_anachronism_1.1.jsonl", "chronologic_en_1.0.jsonl"):
        with pytest.raises(SystemExit):
            builder.main(["frames", "--input", str(inp), "--output", str(tmp_path / "o" / name),
                          "--frames", str(frames)])


def test_builder_lint_warns_on_identity_leaks(builder):
    errors, warnings = builder.lint_frame(
        _rec(1), "A guide by Weed, an American naturalist, published in 2025.", "2025")
    assert not errors
    assert any("Weed" in w for w in warnings) and any("American" in w for w in warnings)


def test_builder_permute_mode(tmp_path, builder):
    recs = [_rec(q, year=1850 + q) for q in range(1, 9)]
    inp = _write_jsonl(tmp_path / "chronologic_en_1.0.jsonl", recs)
    out = tmp_path / "chronologic_en_1.0_wrongframe.jsonl"
    builder.main(["permute", "--input", str(inp), "--output", str(out)])
    got = [json.loads(l) for l in out.read_text().splitlines()]
    assert all(g["candidate_frame_condition"] == "wrongframe" for g in got)
    assert all(g["candidate_metadata_frame"] != g["metadata_frame"] for g in got)
    assert sorted(g["candidate_frame_source_qnum"] for g in got) == list(range(1, 9))


def test_builder_refuses_variant_as_input(tmp_path, builder):
    inp = _write_jsonl(tmp_path / "chronologic_en_1.0_x.jsonl", VARIANT)
    frames = _write_frames(tmp_path / "f.tsv", [(1, GOOD.replace("guide", "manual")),
                                                (2, GOOD.replace("guide", "manual"))])
    with pytest.raises(SystemExit):
        builder.main(["frames", "--input", str(inp), "--output", str(tmp_path / "v_1.0.jsonl"),
                      "--frames", str(frames)])
