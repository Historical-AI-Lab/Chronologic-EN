"""naming.py — Shared filename helpers for the model-as-judge pipeline.

Every script that reads or writes scored_answers/ or generated_answers/ should
import these helpers so that {candidate}__{version} suffixes are identical across
free_generation, judge_scoring, discriminative_scoring, and score_calculation.
"""

from __future__ import annotations

import re
from pathlib import Path


def sanitize(s: str) -> str:
    """Replace characters that are unsafe in filenames with underscores."""
    return re.sub(r"[^a-zA-Z0-9_\-.]", "_", s)


def candidate_tag(model_id: str) -> str:
    """Filesystem-safe tag for a candidate model."""
    return sanitize(model_id)


def judge_tag(model_id: str) -> str:
    """Filesystem-safe tag for a judge model."""
    return sanitize(model_id)


def benchmark_version(benchmark_path) -> str:
    """Extract version string from a benchmark or free-gen filename.

    Takes the LAST X.Y decimal in the stem so that model names containing
    decimals (Qwen2.5, gpt-4.1) do not shadow the benchmark version token.

    Examples:
      'chronologic_en_0.4.jsonl'                        → '0.4'
      'free_gen_Qwen_Qwen2.5-7B-Instruct_ft_0.4.json'  → '0.4'
      'free_gen_gpt-4.1-2025-04-14__0.4.json'          → '0.4'
    Returns 'unknown' if no version pattern found.
    """
    name = Path(benchmark_path).stem
    matches = re.findall(r"\d+\.\d+", name)
    return matches[-1] if matches else "unknown"


def latest_benchmark(booksample_dir) -> Path:
    """Return the path to the highest-versioned chronologic_en_X.Y.jsonl.

    Only exact chronologic_en_X.Y.jsonl names count. Variants such as the public
    chronologic_en_1.0_sample.jsonl are never picked by default: the sample
    would otherwise be scored silently under the full benchmark's "1.0" tag.

    Raises FileNotFoundError if no matching file is found.
    """
    booksample_dir = Path(booksample_dir)
    pattern = re.compile(r"chronologic_en_(\d+)\.(\d+)\.jsonl")
    candidates = [p for p in booksample_dir.glob("chronologic_en_*.jsonl") if pattern.fullmatch(p.name)]
    if not candidates:
        raise FileNotFoundError(
            f"No full benchmark (chronologic_en_X.Y.jsonl) found in {booksample_dir}. "
            "This repository ships only the 100-question public sample. Download the "
            "complete file from the gated dataset at "
            "https://huggingface.co/datasets/chronologic/Chronologic-EN-1.0 and either "
            f"save it as {booksample_dir / 'chronologic_en_1.0.jsonl'} or pass "
            "--benchmark PATH. (To run on the sample deliberately, pass "
            "--benchmark booksample/chronologic_en_1.0_sample.jsonl.)"
        )

    def _ver(p: Path):
        m = pattern.fullmatch(p.name)
        return (int(m.group(1)), int(m.group(2)))

    return max(candidates, key=_ver)


class FrameConditionError(ValueError):
    """A benchmark's candidate-frame override is unmarked or inconsistent."""


def frame_condition_of_records(records) -> str | None:
    """The candidate-frame condition shared by `records`, or None.

    A benchmark variant built by booksample/build_candidate_frame_variant.py
    gives every record a `candidate_metadata_frame` (what the CANDIDATE is
    shown) and a `candidate_frame_condition` naming the manipulation
    (e.g. "anachronism", "wrongframe"). The condition is what keeps such runs
    from sharing a candidate label -- and so every output file and ledger
    row -- with the real run of the same model, so an override without a
    marker, a marker without an override, or two different markers in one
    file are all refused rather than guessed at.
    """
    conditions = set()
    unmarked = []
    for rec in records:
        cond = rec.get("candidate_frame_condition")
        has_frame = bool(rec.get("candidate_metadata_frame"))
        if has_frame and not cond:
            unmarked.append(rec.get("question_number"))
        elif cond and not has_frame:
            raise FrameConditionError(
                f"question_number {rec.get('question_number')!r} carries "
                f"candidate_frame_condition={cond!r} but no candidate_metadata_frame.")
        if cond:
            conditions.add(cond)
    if unmarked:
        raise FrameConditionError(
            f"{len(unmarked)} question(s) carry candidate_metadata_frame without a "
            f"candidate_frame_condition (first: {unmarked[:5]}). Rebuild the variant with "
            f"booksample/build_candidate_frame_variant.py, which marks every record, so "
            f"its runs get a distinct candidate label.")
    if len(conditions) > 1:
        raise FrameConditionError(
            f"benchmark mixes candidate_frame_conditions {sorted(conditions)}; "
            f"one variant file must hold one condition.")
    if conditions:
        cond = conditions.pop()
        if not re.fullmatch(r"[a-z0-9]+", cond):
            raise FrameConditionError(
                f"candidate_frame_condition {cond!r} must be lowercase letters/digits only "
                f"(it becomes a '-{cond}' candidate-label suffix).")
        return cond
    return None


def benchmark_frame_condition(benchmark_path) -> str | None:
    """frame_condition_of_records() for a benchmark JSONL on disk."""
    import json
    with open(benchmark_path, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]
    return frame_condition_of_records(records)


def condition_label(label: str, condition: str | None) -> str:
    """`label` with a '-{condition}' suffix, added once; unchanged if no condition."""
    if not condition:
        return label
    suffix = f"-{condition}"
    return label if label.endswith(suffix) else label + suffix


def scored_answers_filename(
    judge: str,
    candidate_label: str,
    version: str,
    candidate_effort: str = "none",
    judge_effort: str = "none",
) -> str:
    """Canonical filename for a scored-answers output file.

    Format:
      judge_{judge}__{candidate_label}__{version}__c-{ceff}__j-{jeff}.json

    Both effort tokens are always written so runs at different effort levels
    never collide.
    """
    j = judge_tag(judge)
    c = sanitize(candidate_label)
    return f"judge_{j}__{c}__{version}__c-{candidate_effort}__j-{judge_effort}.json"
