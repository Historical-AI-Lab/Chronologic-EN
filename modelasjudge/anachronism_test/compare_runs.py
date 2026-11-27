"""compare_runs.py — one model's original vs. ablated free-generation scores.

    python compare_runs.py gpt-5.4 [--ablations wrongframe anachronism]

For each run label (BASE, BASE-wrongframe, BASE-anachronism, ...) reads the
score JSON written by score_substantive.py, from the working results
(modelasjudge/results/) if present, else from the published copies
(results/freegen/scores/). Style columns come from the matching ledger row
(working ledger first, then results/freegen/chronologic_scores_1.0.csv).

Reports group scores (cloze / generation / knowledge-inference), the pooled
headline, and style fidelity/drift, plus each ablation's drop from the
original.

Paired CIs on the drops: score_substantive.py's bootstrap is seeded
(--seed 20260817) and resamples question indices that depend only on the
seed and the pass/fail and partial-credit counts. So for two runs with equal
seed and counts, the saved overall draws (passfail_draws, partial_draws,
pooled_*_draws) are index-aligned, and their draw-wise differences form a
paired bootstrap. The script checks seed and counts before pairing. Group-level draws are not saved,
so group drops get no CI here.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MJ = HERE.parent
REPO = MJ.parent
SCORE_DIRS = [MJ / "results", REPO / "results" / "freegen" / "scores"]
LEDGERS = [MJ / "results" / "chronologic_scores.csv", REPO / "results" / "freegen" / "chronologic_scores_1.0.csv"]

GROUPS = [("cloze", "grp_cloze"), ("generation", "grp_congen"), ("knowledge/inference", "grp_knowinf")]
DRAWS = [("pass/fail", "passfail"), ("partial", "partial"), ("pooled (equal)", "pooled_equal")]
STYLE = [("date fidelity (E3)", "style_period_fidelity_e3"), ("drift, years (E3)", "style_drift_years_e3"),
         ("human authenticity", "style_authenticity_fidelity")]


def sanitize(s):
    import re
    return re.sub(r"[^a-zA-Z0-9_\-.]", "_", s)


def load_scores(label):
    for d in SCORE_DIRS:
        p = d / f"scores_{sanitize(label)}__1.0.json"
        if p.exists():
            return json.loads(p.read_text()), p
    return None, None


def load_ledger_row(label):
    for p in LEDGERS:
        if p.exists():
            for row in csv.DictReader(open(p, encoding="utf-8")):
                if row.get("candidate_label") == label and row.get("benchmark_version") == "1.0":
                    return row
    return {}


def f(x, scale=100.0, nd=1):
    try:
        return f"{float(x) * scale:.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--ablations", nargs="+", default=["wrongframe", "anachronism"])
    args = ap.parse_args()

    labels = [args.base] + [f"{args.base}-{a}" for a in args.ablations]
    runs = {}
    for lab in labels:
        s, p = load_scores(lab)
        if s is None:
            print(f"(no scores yet for {lab})")
            continue
        runs[lab] = (s, load_ledger_row(lab), p)
    if args.base not in runs:
        raise SystemExit(f"no scores for base {args.base}")
    base, base_row, _ = runs[args.base]

    cols = list(runs)
    print("| | " + " | ".join(cols) + " |")
    print("|---|" + "---|" * len(cols))
    for name, k in GROUPS:
        cells = []
        for lab in cols:
            s = runs[lab][0]
            cell = f"{f(s[k + '_score'])} [{f(s[k + '_lo'])}, {f(s[k + '_hi'])}]"
            if lab != args.base:
                cell += f" (Δ {float(s[k + '_score']) * 100 - float(base[k + '_score']) * 100:+.1f})"
            cells.append(cell)
        print(f"| {name} | " + " | ".join(cells) + " |")
    for name, k in DRAWS:
        cells = []
        for lab in cols:
            s = runs[lab][0]
            cells.append(f"{f(s[k])} [{f(s[k + '_lo'])}, {f(s[k + '_hi'])}]")
        print(f"| {name} | " + " | ".join(cells) + " |")
    for name, k in STYLE:
        cells = []
        for lab in cols:
            v = runs[lab][1].get(k, "")
            cells.append(f(v, scale=1.0) if v not in ("", None) else "—")
        print(f"| {name} | " + " | ".join(cells) + " |")

    print("\nPaired drops vs. original (overall channels; draw-wise differences):")
    for lab in cols[1:]:
        s = runs[lab][0]
        same = (s.get("seed") == base.get("seed") and s.get("n_passfail") == base.get("n_passfail")
                and s.get("n_partial") == base.get("n_partial") and s.get("n_boot") == base.get("n_boot"))
        if not same:
            print(f"  {lab}: seeds/counts differ -- draws not paired")
            continue
        for name, k in DRAWS:
            d = (np.array(s[k + "_draws"]) - np.array(base[k + "_draws"])) * 100
            lo, hi = np.percentile(d, [2.5, 97.5])
            pt = (float(s[k]) - float(base[k])) * 100
            print(f"  {lab:<28} {name:<15} {pt:+6.1f}  [{lo:+.1f}, {hi:+.1f}]")

    print("\nSources:")
    for lab in cols:
        print(f"  {lab}: {runs[lab][2]}")


if __name__ == "__main__":
    main()
