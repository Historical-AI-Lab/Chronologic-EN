"""make_pilot.py — choose the anachronism pilot questions and write their frames.

Picks PER_TYPE questions from each of the eight reasoning types (40 total),
seeded, from the reviewed anachronism_frames_1.0.tsv:

  - within a type, no two questions share an original frame (so the pilot
    sees as many different rewrites as possible);
  - for the four non-cloze types, at least one pick uses "subj" phrasing
    when the type has any, since those are the rewrites most likely to
    confuse a model or draw a demurral.

Writes anachronism_frames_pilot_1.0.tsv (same columns as the full TSV,
gitignored by the same pattern). Then build the pilot benchmark with:

    cd booksample
    python build_candidate_frame_variant.py frames \\
        --frames ../modelasjudge/anachronism_test/anachronism_frames_pilot_1.0.tsv \\
        --only-covered --condition anachronismpilot --require-year 2023 \\
        --output chronologic_anachronism_pilot_1.0.jsonl

The separate condition ("anachronismpilot") gives pilot runs their own label
suffix, so they never resume into or overwrite the full anachronism runs.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "anachronism_frames_1.0.tsv"
OUT = HERE / "anachronism_frames_pilot_1.0.tsv"
PER_TYPE = 5
SEED = 20261126
TYPES = ["phrase_cloze", "sentence_cloze", "topic_sentence", "character_modeling",
         "constrained_generation", "knowledge", "inference", "abstention"]


def pick(rows, rng):
    rows = rows[:]
    rng.shuffle(rows)
    chosen, frames = [], set()
    subj = [r for r in rows if r["phrasing"] == "subj"]
    if subj and any(r["phrasing"] == "decl" for r in rows):  # non-cloze type with a mix
        chosen.append(subj[0])
        frames.add(subj[0]["frame_id"])
    for r in rows:
        if len(chosen) == PER_TYPE:
            break
        if r["frame_id"] not in frames:
            chosen.append(r)
            frames.add(r["frame_id"])
    return chosen


def main():
    with open(SRC, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = reader.fieldnames
        by_type = defaultdict(list)
        for r in reader:
            by_type[r["reasoning_type"]].append(r)

    rng = random.Random(SEED)
    chosen = []
    for t in TYPES:
        got = pick(by_type[t], rng)
        if len(got) < PER_TYPE:
            raise SystemExit(f"{t}: only {len(got)} questions with distinct frames")
        chosen += got
    chosen.sort(key=lambda r: int(r["question_number"]))

    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(chosen)
    print(f"Wrote {len(chosen)} pilot rows to {OUT}")
    for r in chosen:
        print(f"  q{r['question_number']:>3} {r['reasoning_type']:<23} {r['phrasing']:<4} {r['frame_id']}")


if __name__ == "__main__":
    main()
