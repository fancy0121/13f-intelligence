"""Security Semantic Audit CLI (v0.2.2).

python -m thirteenf.research.semantic classify   - build classification artifact
python -m thirteenf.research.semantic audit      - build all Q1-Q7 reports

Outcome-blind: no outcome/returns module is imported here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.database import connect
from thirteenf.research.resolution.coverage import (
    build_observation_frames,
    load_availability,
    load_master,
)
from thirteenf.research.semantic.audit import (
    classify_all,
    compute_missingness,
    compute_q1,
    compute_q2,
    compute_q3,
    compute_q4,
    compute_q5,
    compute_q6,
    compute_q7,
    compute_selection_bias,
    decompose_variant_bias,
    load_classification,
)
from thirteenf.research.semantic.taxonomy import POOLED_TYPES, OPERATING_TYPES


def _md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def cmd_classify(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    class_df = classify_all(conn, args.cache)
    conn.close()
    args.out.mkdir(parents=True, exist_ok=True)
    class_df.to_csv(args.out / "security_semantic_classification.csv", index=False)
    print(class_df["economic_type"].value_counts().to_dict())
    print("classification rows:", len(class_df))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    frames = build_observation_frames(conn)
    if (args.out / "security_semantic_classification.csv").exists():
        class_df = load_classification(args.out / "security_semantic_classification.csv")
    else:
        class_df = classify_all(conn, args.cache)
        class_df.to_csv(args.out / "security_semantic_classification.csv", index=False)
    conn.close()
    master = load_master(args.out / "security_resolution_master.csv")
    avail_path = args.out / "symbol_history_availability.csv"
    availability = load_availability(avail_path) if avail_path.exists() else None

    q1 = compute_q1(class_df, frames)
    q2 = compute_q2(frames, class_df)
    q3 = compute_q3(frames, class_df)
    q4 = compute_q4(master, class_df)
    q5 = compute_q5(master, class_df)
    q6 = compute_q6(frames, master, availability, class_df)
    q7 = compute_q7(frames, class_df, conn)
    sel = compute_selection_bias(frames, class_df)
    miss = compute_missingness(frames, master, availability, class_df)
    vbd = decompose_variant_bias(frames, master, availability, class_df)

    args.out.mkdir(parents=True, exist_ok=True)
    results = {
        "q1_universe_composition": q1,
        "q2_variant_composition": q2,
        "q3_split_composition": q3,
        "q4_resolution_by_type": q4,
        "q5_failure_taxonomy": q5,
        "q6_operating_natural_resolution": q6,
        "q7_operating_vs_pooled": q7,
        "selection_bias": sel,
        "missingness": miss,
        "variant_bias_decomposition": vbd,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.out / "security_semantic_audit_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # Q1
    lines = ["# Security Semantic Composition (v0.2.2)", "",
             f"> Generated: {datetime.now(timezone.utc).isoformat()}", "",
             "## Security level", "",
             _md_table(["economic_type", "n", "pct"], q1["security_level"]), "",
             "## Observation level (O0)", "",
             _md_table(["economic_type", "n", "pct"], q1["observation_level"]), ""]
    (args.out / "security_semantic_composition.md").write_text("\n".join(lines), encoding="utf-8")

    # Q2
    lines = ["# Security Semantic Variant Composition (v0.2.2)", "", "## Observation share by variant", "",
             _md_table(["variant", "economic_type", "n", "pct"],
                       [{"variant": v, **r} for v in ("O0", "O1_2Q", "O1_3Q") for r in q2[v]]), ""]
    (args.out / "security_semantic_variant_composition.md").write_text("\n".join(lines), encoding="utf-8")

    # Q3
    lines = ["# Security Semantic Split Composition (v0.2.2)", "",
             f"SECURITY_TYPE_SPLIT_SHIFT={q3['SECURITY_TYPE_SPLIT_SHIFT']}", "",
             _md_table(["split", "economic_type", "n", "share_pct", "overall_share_pct", "delta_pp"], q3["rows"]), ""]
    (args.out / "security_semantic_split_composition.md").write_text("\n".join(lines), encoding="utf-8")

    # Q4
    lines = ["# Security Type Resolution Breakdown (v0.2.2)", "",
             "Resolver VERIFIED rate by economic type (v0.2.1 rules, unchanged).", "",
             _md_table(["economic_type", "securities", "resolver_verified", "resolution_rate_pct"],
                       [{"economic_type": k, **{kk: vv for kk, vv in v.items() if kk != "status_counts"}}
                        for k, v in q4.items()]), ""]
    (args.out / "security_type_resolution_breakdown.md").write_text("\n".join(lines), encoding="utf-8")

    # Q5
    lines = ["# Resolution Failure Taxonomy (v0.2.2)", "",
             f"Total non-VERIFIED securities: {q5['total_non_verified']}", "",
             _md_table(["failure_reason", "securities", "pct", "top_status"],
                       [{**r, "top_status": json.dumps(r["top_status"], ensure_ascii=False)}
                        for r in q5["rows"]]), ""]
    (args.out / "resolution_failure_taxonomy.md").write_text("\n".join(lines), encoding="utf-8")

    # Q6
    lines = ["# Operating Equity Natural Resolution (v0.2.2)", "",
             "Audit-only view; resolver rules NOT modified.", "",
             _md_table(["variant", "eligible_observations", "resolved_observations", "coverage_pct"],
                       [{"variant": v, **{k: val for k, val in d.items() if k in ("eligible_observations", "resolved_observations", "coverage_pct")}}
                        for v, d in q6.items() if isinstance(d, dict) and "eligible_observations" in d]), "",
             "## Per split (O0)", "",
             _md_table(["split", "n", "resolved", "coverage"],
                       [{"split": p, **q6["O0"][p]} for p in ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined")]), "",
             "## Security level", "",
             _md_table(["operating_securities", "resolver_verified", "rate_pct"],
                       [q6["security_level"]]), ""]
    (args.out / "operating_equity_natural_resolution.md").write_text("\n".join(lines), encoding="utf-8")

    # Q7
    g = q7["groups"]
    lines = ["# Operating vs Pooled Behavior (v0.2.2) - pre-outcome facts", "",
             "## Action rates and structure", "",
             _md_table(["metric", "operating", "pooled", "abs_diff_pp"],
                       [
                           {"metric": f"rate {k}", "operating": g.get("OPERATING", {}).get("action_rates", {}).get(k),
                            "pooled": g.get("POOLED", {}).get("action_rates", {}).get(k),
                            "abs_diff_pp": (lambda a, b: round((a - b) * 100, 3) if a is not None and b is not None else None)(
                                g.get("OPERATING", {}).get("action_rates", {}).get(k),
                                g.get("POOLED", {}).get("action_rates", {}).get(k))}
                           for k in ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")
                       ]),
             "",
             "## Structural descriptors", "",
             _md_table(["metric", "operating", "pooled"],
                       [{"metric": m, "operating": g.get("OPERATING", {}).get(m),
                         "pooled": g.get("POOLED", {}).get(m)}
                        for m in ("n_observations", "turnover_proxy", "persistence_2q_rate",
                                  "persistence_3q_rate", "weight_mean", "weight_median",
                                  "weight_p25", "weight_p75", "positions_per_filing_mean",
                                  "positions_per_filing_median", "managers_per_security_mean",
                                  "reversal_rate")]),
             "",
             f"MANAGER_COMPOSITION_CONFOUNDED={q7['manager_composition_confounded']}",
             f"TIME_COMPOSITION_SENSITIVE={q7['time_composition_sensitive']}",
             "",
             "## Manager control (within-manager operating-pooled positive-rate diff)",
             "",
             _md_table(["manager_id", "operating_positive_rate", "pooled_positive_rate", "diff_pp", "n_operating", "n_pooled"],
                       q7["manager_control"]),
             "",
             "## Time control (per quarter diff)",
             "",
             _md_table(["quarter", "operating_positive_rate", "pooled_positive_rate", "diff_pp", "n"],
                       q7["time_control"]),
             ""]
    (args.out / "operating_vs_pooled_behavior.md").write_text("\n".join(lines), encoding="utf-8")

    # Selection bias
    lines = ["# Security Semantic Selection Bias Audit (v0.2.2)", "",
             "Operating Equity audit set vs Broad universe (pre-outcome).", ""]
    for dim, rows in sel.items():
        if isinstance(rows, list) and rows:
            lines += ["## " + dim, "", _md_table(list(rows[0].keys()), rows), ""]
        elif isinstance(rows, dict):
            lines += ["## " + dim, "", _md_table(list(rows.keys()), [rows]), ""]
    (args.out / "security_semantic_selection_bias_audit.md").write_text("\n".join(lines), encoding="utf-8")

    # Missingness
    lines = ["# Operating Equity Missingness Audit (v0.2.2)", "",
             "Within OPERATING_EQUITY_AUDIT_SET: mapped vs unresolved observations.",
             f"Overall: {json.dumps(miss['overall'], ensure_ascii=False)}", ""]
    for dim, rows in miss.items():
        if dim == "overall":
            continue
        lines += ["## " + dim, "", _md_table(list(rows[0].keys()), rows), ""]
    (args.out / "operating_equity_missingness_audit.md").write_text("\n".join(lines), encoding="utf-8")

    # Variant bias decomposition
    lines = ["# Variant Mapping Bias Decomposition (v0.2.2)", "",
             "Composition effect vs within-type mapping bias.", "",
             _md_table(["variant", "overall_coverage_pct"],
                       [{"variant": v, "overall_coverage_pct": d["overall"]} for v, d in vbd.items()]),
             "",
             "## Within-type coverage by variant", "",
             _md_table(["variant", "economic_type", "coverage_pct"],
                       [{"variant": v, "economic_type": t, "coverage_pct": c}
                        for v, d in vbd.items() for t, c in d["within_type"].items()]),
             ""]
    (args.out / "variant_mapping_bias_decomposition.md").write_text("\n".join(lines), encoding="utf-8")

    print("semantic audit artifacts written")
    print("Q1 obs:", q1["observation_total"], "Q1 sec:", q1["security_total"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thirteenf.research.semantic")
    parser.add_argument("--db", default=str(ROOT / "data" / "thirteenf.db"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "research"))
    parser.add_argument("--cache", default=str(ROOT / "data" / "resolution_cache"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("classify").set_defaults(func=cmd_classify)
    sub.add_parser("audit").set_defaults(func=cmd_audit)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.out = Path(args.out)
    args.cache = Path(args.cache)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

