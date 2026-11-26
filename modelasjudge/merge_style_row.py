"""merge_style_row.py — join a per-candidate style_report_*.json (written by
stylejudge/score_style.py) into the substantive ledger's style_* columns.

A top-level script, not a score_substantive.py subcommand:
score_substantive._resolve is built around a scored-answers file and a draw
bank, and this must run even when score_substantive (stage 11) has not --
`--only style_score` before stage 11 has ever run for a candidate is a real
usage pattern the exit-code contract below exists to make legible.

Usage
-----
    python merge_style_row.py --style-json PATH [key options]

      --style-json PATH      (required) results/style_report_*.json
      --scored-file PATH     derive the key from scored_answers/judge_*.json
                             (+ its companion _btcontext.json)
      --benchmark-version / --candidate-label / --candidate-effort /
      --judge / --judge-effort / --bt-tag     explicit key components;
                             override --scored-file, which overrides the
                             style JSON's own (partial) identity
      --ledger PATH          default substantive_artifacts.ledger_path()
      --create-missing       create the ledger row if the key is absent
      --require-ledger       exit 1 (instead of 0) when the key is incomplete
      --dry-run              print the row dict and resolved key; write nothing

Exit codes: 0 success (merged, or dry-run, or incomplete key without
--require-ledger); 1 incomplete key with --require-ledger; 2 the key
resolved completely but no ledger row matched it (run score_substantive
first, or pass --create-missing).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from substantive import artifacts as substantive_artifacts
from substantive import ledger

EXPECTED_SCHEMA_VERSION = "stylejudge-2.0"

# Dotted-path (with [index] for lists) lookups into the style_report_*.json
# schema -> ledger column. Covers every style_* column in ledger.COLUMNS.
# Split into three groups so a single-channel report (score_style.py
# --channels date|auth) or a suffixed _e3 merge writes only the columns it
# actually has values for -- never KeyErrors on the missing channel's paths,
# and never touches the frozen unsuffixed columns of the other family.
COHORT_LEDGER_MAP = {
    "style_cohort_id": "provenance.style_run_id",
}
DATE_LEDGER_MAP = {
    "style_period_fidelity": "e1.headline.score",
    "style_period_fidelity_lo": "e1.headline.ci95[0]",
    "style_period_fidelity_hi": "e1.headline.ci95[1]",
    "style_w1": "e1.wasserstein.w1_observed",
    "style_w1_null_mean": "e1.wasserstein.w1_null_mean",
    "style_drift_years": "e1.years.drift_mean",
    "style_dispersion_mae": "e1.years.dispersion_mae",
    "style_T_drift": "e1.conformal.drift",
    "style_T_disp": "e1.conformal.dispersion",
    "style_T_KS": "diagnostics.ks",
}
AUTH_LEDGER_MAP = {
    "style_authenticity_fidelity": "e2.headline.score",
    "style_authenticity_fidelity_lo": "e2.headline.ci95[0]",
    "style_authenticity_fidelity_hi": "e2.headline.ci95[1]",
    "style_T_E2": "e2.conformal.mean_q",
}
# The historical flat map (cohort + date + auth), still the default for a
# legacy `both` report with no `channels` field.
STYLE_LEDGER_MAP = {**COHORT_LEDGER_MAP, **DATE_LEDGER_MAP, **AUTH_LEDGER_MAP}

_PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]")


def _suffix_col(col: str, suffix: str) -> str:
    """`style_w1` + `_e3` -> `style_w1_e3`; `style_period_fidelity_lo` + `_e3`
    -> `style_period_fidelity_e3_lo` (suffix goes before a trailing _lo/_hi so
    the result matches ledger.COLUMNS' `style_*_e3[_lo|_hi]` names)."""
    if not suffix:
        return col
    for tail in ("_lo", "_hi"):
        if col.endswith(tail):
            return col[:-len(tail)] + suffix + tail
    return col + suffix


def _get_path(data: dict, dotted_path: str):
    """Resolve a dotted path like 'e1.headline.ci95[0]' against nested
    dicts/lists. Raises KeyError/IndexError/TypeError on a schema mismatch
    -- deliberately not swallowed, so a stale or malformed style JSON fails
    loudly rather than silently writing an empty ledger cell."""
    cur = data
    for tok in _PATH_TOKEN_RE.findall(dotted_path):
        if tok.startswith("["):
            cur = cur[int(tok[1:-1])]
        else:
            cur = cur[tok]
    return cur


def build_updates(style_data: dict, *, column_suffix: str = "") -> dict:
    """Map the style report into ledger column updates.

    `column_suffix` non-empty (e.g. `_e3`): the date-derived family ONLY,
    every column name suffixed via `_suffix_col`, plus the two provenance
    columns `style_date_run_id{suffix}` / `style_n_e1_abstained{suffix}` read
    leniently with `.get` (a missing key is a blank cell, not a crash --
    `_get_path` would raise and break legacy re-merges).

    No suffix (legacy path): the column set is chosen by the report's own
    `channels` field so a single-channel report writes only its own family --
    `auth` -> authenticity + cohort_id, `date` -> date + cohort_id,
    `both`/absent -> the full historical map.
    """
    if column_suffix:
        updates = {_suffix_col(col, column_suffix): _get_path(style_data, path)
                   for col, path in DATE_LEDGER_MAP.items()}
        updates["style_date_run_id" + column_suffix] = (
            style_data.get("provenance", {}).get("style_run_id"))
        updates["style_n_e1_abstained" + column_suffix] = (
            style_data.get("e1", {}).get("n_abstained"))
        return updates

    channels = style_data.get("channels", "both")
    if channels == "auth":
        selected = {**COHORT_LEDGER_MAP, **AUTH_LEDGER_MAP}
    elif channels == "date":
        selected = {**COHORT_LEDGER_MAP, **DATE_LEDGER_MAP}
    else:
        selected = STYLE_LEDGER_MAP
    return {col: _get_path(style_data, path) for col, path in selected.items()}


def resolve_key(args, style_data: dict) -> dict:
    """explicit flags > --scored-file > the style JSON's own (partial:
    benchmark_version + candidate_label only -- never sufficient alone)
    identity."""
    key = {}
    model = style_data.get("model", {})
    key["benchmark_version"] = model.get("benchmark_version")
    key["candidate_label"] = model.get("candidate_label")

    if args.scored_file:
        scored_path = Path(args.scored_file)
        scored = json.loads(scored_path.read_text(encoding="utf-8"))
        key["benchmark_version"] = scored.get("benchmark_version", key.get("benchmark_version"))
        key["candidate_label"] = (scored.get("candidate_label")
                                  or scored.get("candidate_model") or key.get("candidate_label"))
        key["candidate_effort"] = scored.get("candidate_reasoning_effort", "none")
        key["judge"] = scored.get("judge_model")
        key["judge_effort"] = scored.get("reasoning_effort", "none")
        bt_scored_path = scored_path.parent / f"{scored_path.stem}_btcontext.json"
        if bt_scored_path.exists():
            bt_scored = json.loads(bt_scored_path.read_text(encoding="utf-8"))
            key["bt_tag"] = bt_scored.get("bt_context", {}).get("artifacts_tag")

    for name in ledger.KEY_COLUMNS:
        cli_val = getattr(args, name, None)
        if cli_val is not None:
            key[name] = cli_val

    return key


def _missing_key_columns(key: dict) -> list:
    return [c for c in ledger.KEY_COLUMNS if not key.get(c)]


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    style_path = Path(args.style_json)
    style_data = json.loads(style_path.read_text(encoding="utf-8"))
    schema_version = style_data.get("schema_version")
    if schema_version != EXPECTED_SCHEMA_VERSION:
        sys.exit(f"ERROR: {style_path} has schema_version={schema_version!r}, "
                 f"expected {EXPECTED_SCHEMA_VERSION!r}")

    updates = build_updates(style_data, column_suffix=args.column_suffix)
    key = resolve_key(args, style_data)
    missing = _missing_key_columns(key)

    if args.dry_run:
        print(f"resolved key: {key}")
        print("style row updates:")
        for k, v in updates.items():
            print(f"  {k} = {v}")
        if missing:
            print(f"incomplete key (missing {missing}) -- not touching the ledger")
        else:
            print("key is complete; a real run would attempt a ledger merge")
        return 0

    if missing:
        print(f"style row for {style_data.get('model', {}).get('candidate_label')}: "
             + ", ".join(f"{k}={v}" for k, v in updates.items()))
        print(f"incomplete key (missing {missing}) -- ledger NOT touched")
        if args.require_ledger:
            return 1
        return 0

    ledger_path = Path(args.ledger) if args.ledger else substantive_artifacts.ledger_path()
    ok = ledger.merge_columns(key, updates, path=ledger_path, create_missing=args.create_missing)
    if not ok:
        print(f"wrote {style_path}; no ledger row matched yet for key {key} "
             f"-- run score_substantive first, or pass --create-missing")
        return 2

    print(f"merged style columns into {ledger_path} for key {key}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--style-json", required=True)
    p.add_argument("--scored-file", default=None)
    p.add_argument("--benchmark-version", default=None)
    p.add_argument("--candidate-label", default=None)
    p.add_argument("--candidate-effort", default=None)
    p.add_argument("--judge", default=None)
    p.add_argument("--judge-effort", default=None)
    p.add_argument("--bt-tag", default=None)
    p.add_argument("--ledger", default=None)
    p.add_argument("--column-suffix", default="",
                  help="append to every mapped ledger column name (before a trailing "
                       "_lo/_hi). Non-empty => date-derived columns only, plus "
                       "style_date_run_id{suffix} / style_n_e1_abstained{suffix}. "
                       "Use `_e3` for the DeBERTa date-judge family.")
    p.add_argument("--create-missing", action="store_true")
    p.add_argument("--require-ledger", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


if __name__ == "__main__":
    sys.exit(main())
