"""build_candidate_frame_variant.py — build a CANDIDATE-VIEW variant of a
Chronologic benchmark, in which the model being evaluated is shown a different
metadata frame than the judges grade against.

Ported from GPT-1914/chronologic/booksample/build_wrong_context_variant.py
(the builder behind the paper's "GPT-5.4 wrong contexts" row) and generalized
to two modes:

  permute   The original wrongframe recipe: each question borrows another
            question's metadata_frame via a derangement computed within four
            context buckets (below), avoiding self-, same-book- and
            same-text donors. Defaults reproduce the original seed.

  frames    Hand-written frames from a reviewed TSV/CSV (one row per
            question_number), e.g. the anachronism frames that move every
            context to 2025 and strip authorship, nationality, stance,
            profession and gender.

Both modes leave every original field byte-identical -- in particular
metadata_frame and substantive_metadata_frame, which every judge, reliability
and scoring stage reads as "context" -- and ADD:

  candidate_metadata_frame    what the candidate is shown instead
                              (modelasjudge/free_generation.build_prompts()
                              is the only reader)
  candidate_frame_condition   the condition name ("wrongframe",
                              "anachronism", ...). run_pipeline.py and
                              free_generation.py append "-{condition}" to the
                              candidate label from it, and refuse a variant
                              whose records lack it.
  candidate_frame_source_qnum / _htid   (permute mode only) the donor

Why the output keeps the input's benchmark version: nothing the
instrument-scoped stages of run_pipeline.py read has changed, so a matching
version lets them reuse the real benchmark's anchors, LOO set, calibration
and reliability files instead of recomputing ~15,000 judge calls. The script
refuses an --output whose last X.Y differs from --input's. Separation from
the real model runs comes from the condition suffix on the candidate label.

Permute-mode buckets (from the original ExperimentPlan.md design; note this
is NOT within reasoning type -- about half of donors cross reasoning types):

    world      -- frame_type == "world_context"
    character  -- frame_type == "book_context" and reasoning_type == "character_modeling"
    book_other -- frame_type == "book_context", any other reasoning_type
    passage    -- frame_type == "passage_context"

Frames-mode file: a header row is required. Columns:
    question_number   (or qnum)
    <frame column>    named by --frame-column (default anachronism_frame)
    original_frame    optional; if present, must equal the benchmark's
                      metadata_frame (catches a TSV built from another file)
Other columns (reasoning_type, mode, flags, notes) are ignored. Delimiter is
tab for .tsv, comma otherwise.

Usage:
    python build_candidate_frame_variant.py frames \\
        --frames ../modelasjudge/anachronism_test/anachronism_frames_1.0.tsv \\
        --require-year 2025 --dry-run
    python build_candidate_frame_variant.py frames --frames ... --require-year 2025 \\
        --sha-record ../modelasjudge/anachronism_test/benchmark_sha256.txt
    python build_candidate_frame_variant.py permute --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BOOKSAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BOOKSAMPLE_DIR.parent
DEFAULT_INPUT = BOOKSAMPLE_DIR / "chronologic_en_1.0.jsonl"
DEFAULT_OUTPUTS = {
    "frames": BOOKSAMPLE_DIR / "chronologic_anachronism_1.0.jsonl",
    "permute": BOOKSAMPLE_DIR / "chronologic_en_1.0_wrongframe.jsonl",
}
DEFAULT_CONDITIONS = {"frames": "anachronism", "permute": "wrongframe"}

sys.path.insert(0, str(REPO_ROOT / "modelasjudge"))
from naming import benchmark_version, frame_condition_of_records  # noqa: E402

ADDED_KEYS = {"candidate_metadata_frame", "candidate_frame_condition",
              "candidate_frame_source_qnum", "candidate_frame_source_htid"}


def load_records(path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# permute mode (ported unchanged from build_wrong_context_variant.py)
# ---------------------------------------------------------------------------

def bucket_of(record: dict) -> str:
    frame_type = record.get("frame_type")
    reasoning_type = record.get("reasoning_type")
    if frame_type == "world_context":
        return "world"
    if frame_type == "book_context":
        return "character" if reasoning_type == "character_modeling" else "book_other"
    if frame_type == "passage_context":
        return "passage"
    raise ValueError(
        f"question_number {record.get('question_number')!r} has unrecognized "
        f"frame_type {frame_type!r}"
    )


def bucket_records(records: list[dict]) -> dict[str, list[int]]:
    buckets: dict[str, list[int]] = {"world": [], "character": [], "book_other": [], "passage": []}
    for i, rec in enumerate(records):
        buckets[bucket_of(rec)].append(i)
    return buckets


def find_bucket_derangement(indices, records, rng, max_tries):
    """Find a same-position-, same-htid-, and same-frame-avoiding derangement
    of `indices`: shuffle once, then repair violations with targeted random
    swaps, keeping any swap that doesn't increase the violation count.

    Returns ({global index: donor global index}, repair steps used), or
    (None, max_tries) if no valid derangement was found.
    """
    n = len(indices)
    htids = [records[i]["source_htid"] for i in indices]
    frames = [records[i]["metadata_frame"] for i in indices]

    def is_bad(pos, order):
        return (
            order[pos] == pos
            or htids[order[pos]] == htids[pos]
            or frames[order[pos]] == frames[pos]
        )

    order = list(range(n))
    rng.shuffle(order)
    bad = [i for i in range(n) if is_bad(i, order)]

    tries = 0
    while bad and tries < max_tries:
        tries += 1
        i = rng.choice(bad)
        j = rng.choice(bad) if len(bad) > 1 and rng.random() < 0.7 else rng.randrange(n)
        if i == j:
            continue
        order[i], order[j] = order[j], order[i]
        new_bad = [k for k in range(n) if is_bad(k, order)]
        if len(new_bad) <= len(bad):
            bad = new_bad
        else:
            order[i], order[j] = order[j], order[i]

    if bad:
        return None, tries
    return {indices[i]: indices[order[i]] for i in range(n)}, tries


def permuted_variant(records, condition, seed, max_tries):
    buckets = bucket_records(records)
    rng = random.Random(seed)
    donor_of: dict[int, int] = {}
    for name, indices in buckets.items():
        result, steps = find_bucket_derangement(indices, records, rng, max_tries)
        if result is None:
            raise SystemExit(
                f"failed to find a same-book-avoiding derangement for bucket '{name}' "
                f"({len(indices)} records) in {max_tries} tries (seed={seed}). "
                f"Try a different --seed or raise --max-tries.")
        donor_of.update(result)
        donor_books = {records[result[i]]["source_htid"] for i in indices}
        print(f"Bucket '{name}': {len(indices)} questions, {steps} repair steps, "
              f"{len(donor_books)} distinct donor books")

    out = []
    for i, rec in enumerate(records):
        donor = records[donor_of[i]]
        new_rec = dict(rec)
        new_rec["candidate_metadata_frame"] = donor["metadata_frame"]
        new_rec["candidate_frame_condition"] = condition
        new_rec["candidate_frame_source_qnum"] = donor["question_number"]
        new_rec["candidate_frame_source_htid"] = donor["source_htid"]
        out.append(new_rec)
    return out


# ---------------------------------------------------------------------------
# frames mode
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return " ".join((s or "").split())


def load_frames(path, frame_column) -> dict[str, str]:
    """{question_number (str): frame} from a headed TSV/CSV."""
    path = Path(path)
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        fields = reader.fieldnames or []
        qcol = "question_number" if "question_number" in fields else "qnum" if "qnum" in fields else None
        if qcol is None or frame_column not in fields:
            raise SystemExit(
                f"{path}: header must include question_number (or qnum) and "
                f"{frame_column!r}; found {fields}")
        frames, originals = {}, {}
        for lineno, row in enumerate(reader, start=2):
            q = (row.get(qcol) or "").strip()
            if not q:
                continue
            if q in frames:
                raise SystemExit(f"{path}:{lineno}: duplicate question_number {q}")
            frames[q] = (row.get(frame_column) or "").strip()
            if "original_frame" in fields:
                originals[q] = row.get("original_frame") or ""
    return frames, originals


YEAR_RE = re.compile(r"\b(1[5-9]\d\d|20\d\d)s?\b")


def lint_frame(rec: dict, frame: str, require_year: str | None):
    """(errors, warnings) for one candidate frame.

    Errors block the build: empty frame, frame identical to the true one, and
    (with require_year) a missing target year or any other year. Warnings are
    possible identity leaks for the human reviewer: author name tokens, the
    source title, the author's nationality.
    """
    errors, warnings = [], []
    if not frame:
        return ["empty frame"], warnings
    if _norm(frame) == _norm(rec.get("metadata_frame", "")):
        errors.append("identical to the true metadata_frame")
    if require_year:
        years = {m.group(1) for m in YEAR_RE.finditer(frame)}
        if require_year not in years:
            errors.append(f"does not mention {require_year}")
        other = sorted(years - {require_year})
        if other:
            errors.append(f"mentions other year(s) {other}")
    low = frame.lower()
    for tok in re.split(r"[\s,.;:()]+", rec.get("source_author") or ""):
        if len(tok) > 3 and tok[0].isupper() and re.search(rf"\b{re.escape(tok)}\b", frame):
            warnings.append(f"author token {tok!r}")
    title = (rec.get("source_title") or "").strip()
    if len(title) > 12 and title[:25].lower() in low:
        warnings.append("source title")
    nat = (rec.get("author_nationality") or "").strip()
    if nat and nat.lower() not in {"unknown", "us"} and re.search(rf"\b{re.escape(nat.lower())}\b", low):
        warnings.append(f"nationality {nat!r}")
    return errors, warnings


def framed_variant(records, frames, originals, condition, require_year, only_covered):
    by_q = {str(r["question_number"]): r for r in records}
    unknown = sorted(set(frames) - set(by_q), key=lambda q: (len(q), q))
    if unknown:
        raise SystemExit(f"frames file has question_numbers not in the benchmark: {unknown[:20]}")
    missing = [q for q in by_q if q not in frames]
    if missing and not only_covered:
        raise SystemExit(
            f"{len(missing)} benchmark questions have no frame (first: {missing[:10]}). A partial "
            f"variant would show those questions their TRUE frame under the variant label. "
            f"Pass --only-covered to write just the covered questions (pilot runs).")

    errors, warnings = [], []
    for q, frame in frames.items():
        rec = by_q[q]
        if q in originals and _norm(originals[q]) != _norm(rec.get("metadata_frame", "")):
            errors.append(f"q{q}: original_frame column does not match the benchmark's metadata_frame")
        e, w = lint_frame(rec, frame, require_year)
        errors += [f"q{q} [{rec.get('reasoning_type')}]: {x}" for x in e]
        warnings += [f"q{q} [{rec.get('reasoning_type')}]: {x}" for x in w]
    if warnings:
        print(f"\n{len(warnings)} possible identity leak(s) -- review, not blocking:")
        for w in warnings:
            print("  " + w)
    if errors:
        raise SystemExit(f"\n{len(errors)} frame error(s):\n  " + "\n  ".join(errors))

    out = []
    for rec in records:
        q = str(rec["question_number"])
        if q not in frames:
            continue
        new_rec = dict(rec)
        new_rec["candidate_metadata_frame"] = frames[q]
        new_rec["candidate_frame_condition"] = condition
        out.append(new_rec)
    return out


# ---------------------------------------------------------------------------
# shared checks and output
# ---------------------------------------------------------------------------

def verify_variant(records, out, *, allow_subset=False):
    """Every original field unchanged; every record carries a distinct candidate
    frame and the single condition. Raises SystemExit on any violation."""
    by_q = {r["question_number"]: r for r in records}
    out_q = [r["question_number"] for r in out]
    if len(set(out_q)) != len(out_q):
        raise SystemExit("internal error: duplicate question_number in output")
    if not allow_subset and set(out_q) != set(by_q):
        raise SystemExit("internal error: question_number set changed")
    for var in out:
        orig = by_q[var["question_number"]]
        for k, v in orig.items():
            if k in ADDED_KEYS:
                raise SystemExit(f"input already carries {k!r} (q{orig['question_number']}); "
                                 f"build from the real benchmark, not a variant")
            if var.get(k) != v:
                raise SystemExit(f"internal error: q{orig['question_number']} field {k!r} changed")
        if _norm(var["candidate_metadata_frame"]) == _norm(orig["metadata_frame"]):
            raise SystemExit(f"q{orig['question_number']}: candidate frame equals true frame")
    frame_condition_of_records(out)  # raises if unmarked/mixed


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["frames", "permute"])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--condition", default=None,
                        help="Condition name (default: anachronism for frames, wrongframe for "
                             "permute). Lowercase letters/digits; becomes a label suffix.")
    parser.add_argument("--frames", type=Path, help="frames mode: reviewed TSV/CSV")
    parser.add_argument("--frame-column", default="anachronism_frame")
    parser.add_argument("--require-year", default=None, metavar="YYYY",
                        help="frames mode: every frame must mention YYYY and no other year")
    parser.add_argument("--only-covered", action="store_true",
                        help="frames mode: write only questions present in --frames (pilots)")
    parser.add_argument("--seed", type=int, default=20260824, help="permute mode")
    parser.add_argument("--max-tries", type=int, default=5000, help="permute mode")
    parser.add_argument("--sha-record", type=Path, default=None,
                        help="Append '<sha256>  <output name>  <UTC time>' to this file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    output = args.output or DEFAULT_OUTPUTS[args.mode]
    condition = args.condition or DEFAULT_CONDITIONS[args.mode]

    in_version, out_version = benchmark_version(str(args.input)), benchmark_version(str(output))
    if out_version != in_version:
        raise SystemExit(
            f"--output {output} resolves to benchmark_version={out_version!r}, but --input "
            f"resolves to {in_version!r}. The output must keep the input's version so the "
            f"instrument stages of run_pipeline.py reuse the real benchmark's artifacts.")
    if output.name.startswith("chronologic_en_") and re.fullmatch(r"chronologic_en_\d+\.\d+\.jsonl", output.name):
        raise SystemExit(f"--output {output.name} would be picked up as the real benchmark "
                         f"by naming.latest_benchmark(); choose another name.")

    records = load_records(args.input)
    if args.mode == "permute":
        out = permuted_variant(records, condition, args.seed, args.max_tries)
    else:
        if not args.frames:
            parser.error("frames mode requires --frames")
        frames, originals = load_frames(args.frames, args.frame_column)
        out = framed_variant(records, frames, originals, condition,
                             args.require_year, args.only_covered)
    verify_variant(records, out, allow_subset=args.only_covered)

    print(f"\n{len(out)}/{len(records)} questions, condition={condition!r}, "
          f"benchmark_version={out_version}")
    for rec in out[:3]:
        print(f"  q{rec['question_number']}\n    judge sees:     {rec['metadata_frame'][:110]}"
              f"\n    candidate sees: {rec['candidate_metadata_frame'][:110]}")
    if args.dry_run:
        print(f"\n--dry-run: nothing written (would write {output})")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        for rec in out:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    digest = sha256_of(output)
    print(f"\nWrote {len(out)} questions to {output}\nsha256 {digest}")
    if args.sha_record:
        args.sha_record.parent.mkdir(parents=True, exist_ok=True)
        with open(args.sha_record, "a", encoding="utf-8") as fh:
            fh.write(f"{digest}  {output.name}  {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}\n")


if __name__ == "__main__":
    main()
