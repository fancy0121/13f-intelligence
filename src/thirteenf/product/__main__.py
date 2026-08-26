"""Product harness CLI (v0.4).

python -m thirteenf.product manifest   - build task dev/holdout manifest
python -m thirteenf.product validate   - run dev/holdout tasks, write validation report
python -m thirteenf.product snapshot   - deterministic query snapshot (reproducibility)
python -m thirteenf.product obs-start  - create a real-use episode (pre-use)
python -m thirteenf.product obs-finish - finish an episode (post-use)
python -m thirteenf.product obs-list   - list episodes
python -m thirteenf.product obs-report - aggregate + write observation status report
python -m thirteenf.product obs-export - export episodes CSV/JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.evidence import ProductStore
from thirteenf.product.observation import ObservationStore
from thirteenf.product.tasks import (
    build_task_universe,
    load_manifest,
    split_tasks,
    write_manifest,
)


def _store(out: Path) -> ProductStore:
    return ProductStore(
        ROOT / "data" / "thirteenf.db",
        ROOT / "reports" / "research" / "security_resolution_master.csv",
        ROOT / "reports" / "research" / "security_semantic_classification.csv",
        ROOT / "config" / "managers.csv",
    )


def cmd_manifest(args: argparse.Namespace) -> int:
    store = _store(args.out)
    tasks = split_tasks(
        build_task_universe(store, max_per_category=args.max_per_category, max_scan=args.max_scan)
    )
    store.close()
    path = args.out / "product_task_manifest.csv"
    write_manifest(tasks, path)
    dev = sum(1 for t in tasks if t["part"] == "development")
    hold = sum(1 for t in tasks if t["part"] == "holdout")
    summary = {
        "total_tasks": len(tasks),
        "development": dev,
        "holdout": hold,
        "categories": sorted({t["category"] for t in tasks}),
    }
    (args.out / "product_task_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    store = _store(args.out)
    df = load_manifest(args.out / "product_task_manifest.csv")
    rows = []
    for _, t in df.iterrows():
        key = t["key"]
        if t["kind"] == "security":
            ev = store.security_evidence(key)
            ok = ev is not None and ev.cusip and ev.resolution_status and ev.activity_counts
            rows.append({
                "task_id": t["task_id"], "kind": t["kind"], "part": t["part"],
                "category": t["category"], "retrievable": bool(ok),
                "note": "" if ok else "NOT_RETRIEVABLE",
            })
        else:
            ev = store.manager_evidence(int(key))
            ok = ev is not None and ev.latest_changes is not None
            rows.append({
                "task_id": t["task_id"], "kind": t["kind"], "part": t["part"],
                "category": t["category"], "retrievable": bool(ok),
                "note": "" if ok else "NOT_RETRIEVABLE",
            })
    store.close()
    dev_ok = sum(1 for r in rows if r["part"] == "development" and r["retrievable"])
    dev_n = sum(1 for r in rows if r["part"] == "development")
    hold_ok = sum(1 for r in rows if r["part"] == "holdout" and r["retrievable"])
    hold_n = sum(1 for r in rows if r["part"] == "holdout")
    lines = [
        "# Product Task Validation (v0.4)",
        "",
        f"Development: {dev_ok}/{dev_n} retrievable",
        f"Holdout: {hold_ok}/{hold_n} retrievable",
        "",
        "## By category (holdout)",
        "",
        "| category | n | retrievable |",
        "|---|---|---|",
    ]
    cats = {}
    for r in rows:
        if r["part"] != "holdout":
            continue
        cats.setdefault(r["category"], [0, 0])
        cats[r["category"]][1] += 1
        if r["retrievable"]:
            cats[r["category"]][0] += 1
    for cat, (ok, n) in sorted(cats.items()):
        lines.append(f"| {cat} | {n} | {ok} |")
    lines.append("")
    (args.out / "product_task_validation.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"dev {dev_ok}/{dev_n} holdout {hold_ok}/{hold_n}")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    store = _store(args.out)
    period = store.latest_period() or ""
    snap = {
        "period": period,
        "event_counts": store.event_counts(period),
        "manager_updates": store.manager_update_counts(period),
        "stale_managers": len(store.stale_manager_ids(period)),
        "amendment_count": store.amendment_count(period),
        "resolution_summary": store.resolution_summary(),
        "managers": [m["name"] for m in store.managers_list()],
        "manager_evidence": [],
        "security_evidence": [],
        "activity_explorer_sample": store.activity_explorer("independent_add_manager_count", limit=20),
    }
    for m in store.managers_list()[:5]:
        ev = store.manager_evidence(m["manager_id"])
        if ev:
            snap["manager_evidence"].append({
                "manager_id": ev.manager_id,
                "latest_report_period": ev.latest_report_period,
                "position_count": ev.position_count,
                "change_counts": {k: len(v) for k, v in ev.latest_changes.items()},
            })
    for t in ["02079K305", "30303M102", "594918104"]:
        ev = store.security_evidence(t)
        if ev:
            snap["security_evidence"].append({
                "cusip": ev.cusip,
                "resolution_status": ev.resolution_status,
                "holder_entity_count": ev.holder_entity_count,
                "activity_counts": ev.activity_counts,
                "activity_state": ev.activity_state,
                "repeated_add": ev.repeated_add_manager_count,
                "repeated_reduce": ev.repeated_reduce_manager_count,
            })
    store.close()
    (args.out / "product_query_snapshot.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("snapshot written")
    return 0


def _obs_store(args) -> ObservationStore:
    return ObservationStore(args.obs_dir)


def cmd_obs_start(args: argparse.Namespace) -> int:
    store = _obs_store(args)
    ep = store.start_episode(
        {
            "target_type": args.target_type,
            "target_id": args.target_id,
            "target_label": args.target_label,
            "is_portfolio_target": args.portfolio_target,
            "familiarity_class": args.familiarity,
            "research_question": args.question,
            "pre_use_knowledge": args.knowledge,
            "pre_use_assumptions": args.assumptions,
            "pre_use_uncertainties": args.uncertainties,
            "planned_next_step": args.next_step,
            "baseline_method": args.baseline,
            "episode_cluster_id": args.cluster,
        }
    )
    print(json.dumps({"episode_id": ep["episode_id"], "created_at": ep["created_at"]}, ensure_ascii=False))
    return 0


def cmd_obs_finish(args: argparse.Namespace) -> int:
    store = _obs_store(args)
    flags = {
        "new_fact_found": args.new_fact, "contradicting_fact_found": args.contradicting,
        "stale_assumption_corrected": args.stale_corrected,
        "quality_risk_discovered": args.quality_risk,
        "research_path_changed": args.path_changed,
        "research_time_saved": args.time_saved,
        "no_incremental_information": args.no_incremental,
        "estimated_manual_effort_bucket": args.effort_bucket,
        "misuse_risk": args.misuse_risk,
        "misuse_type": args.misuse_type,
        "product_design_issue": args.design_issue,
        "post_use_next_step": args.post_next,
        "notes": args.notes,
        "synthetic": args.synthetic,
        "product_error": args.product_error,
    }
    ep = store.finish_episode(args.episode_id, flags)
    if ep is None:
        print("episode not found")
        return 1
    print(json.dumps({"episode_id": ep["episode_id"], "validity": ep["episode_validity"]}, ensure_ascii=False))
    return 0


def cmd_obs_list(args: argparse.Namespace) -> int:
    store = _obs_store(args)
    for e in store.episodes():
        print(e["episode_id"], e["episode_validity"], e["target_type"], e.get("target_label", ""))
    return 0


def cmd_obs_report(args: argparse.Namespace) -> int:
    store = _obs_store(args)
    agg = store.aggregate()
    verdict = agg["utility_verdict"]
    lines = [
        "# Real-Use Observation Status (v0.5)",
        "",
        f"> Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"VALID episodes: {agg['valid_episodes']} / target {20}",
        f"Raw episodes: {agg['raw_episode_count']} | unique targets: {agg['unique_target_count']} "
        f"| clustered effective: {agg['clustered_effective_count']}",
        "",
        f"REAL_WORLD_EVIDENCE_UTILITY={verdict}",
        "",
        "## Utility metrics (valid episodes only)",
        "",
        "| metric | value |",
        "|---|---|",
    ]
    for k in (
        "incremental_information_rate", "research_path_change_rate",
        "no_incremental_information_rate", "contradiction_exposure_rate",
        "quality_risk_discovery_rate", "stale_assumption_corrected_rate",
        "portfolio_share",
    ):
        lines.append(f"| {k} | {agg[k]} |")
    lines += [
        "",
        "## Scenario / familiarity / effort / misuse",
        "",
        f"- scenario: {agg['scenario_breakdown']}",
        f"- familiarity: {agg['familiarity_breakdown']}",
        f"- effort buckets: {agg['manual_effort_buckets']}",
        f"- misuse risk: {agg['misuse_risk_counts']}",
        f"- product-design-induced misuse: {agg['product_design_induced_misuse']}",
        f"- product versions: {agg['product_version_breakdown']}",
        "",
        "## Observation mix",
        "",
        "- security >=8: " + ("OK" if agg["scenario_breakdown"].get("security", 0) >= 8 else "OBSERVATION_MIX_INCOMPLETE"),
        "- manager >=4: " + ("OK" if agg["scenario_breakdown"].get("manager", 0) >= 4 else "OBSERVATION_MIX_INCOMPLETE"),
        "- portfolio <=40%: " + ("OK" if agg["portfolio_share"] <= 0.4 else "OBSERVATION_MIX_INCOMPLETE"),
        "- unfamiliar >=5: " + ("OK" if agg["familiarity_breakdown"].get("unfamiliar", 0) >= 5 else "OBSERVATION_MIX_INCOMPLETE"),
        "",
        "When fewer than 20 VALID episodes exist, no real-world utility "
        "conclusion is drawn.",
        "",
    ]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "real_use_observation_status.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(agg, ensure_ascii=False, indent=2))
    return 0


def cmd_obs_export(args: argparse.Namespace) -> int:
    store = _obs_store(args)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.csv:
        store.export_csv(args.out / "real_use_episodes.csv")
        print("exported CSV")
    if args.json:
        store.export_json(args.out / "real_use_episodes.json")
        print("exported JSON")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thirteenf.product")
    parser.add_argument("--out", default=str(ROOT / "reports" / "product"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("manifest")
    p.add_argument("--max-per-category", type=int, default=40)
    p.add_argument("--max-scan", type=int, default=4000)
    p.set_defaults(func=cmd_manifest)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    sub.add_parser("snapshot").set_defaults(func=cmd_snapshot)
    parser.add_argument("--obs-dir", default=str(ROOT / "data" / "real_use"))

    p = sub.add_parser("obs-start")
    p.add_argument("--target-type", required=True, choices=["security", "manager", "portfolio"])
    p.add_argument("--target-id", default="")
    p.add_argument("--target-label", default="")
    p.add_argument("--portfolio-target", default="false")
    p.add_argument("--familiarity", default="UNKNOWN", choices=["familiar", "unfamiliar", "UNKNOWN"])
    p.add_argument("--question", required=True)
    p.add_argument("--knowledge", default="UNKNOWN")
    p.add_argument("--assumptions", default="UNKNOWN")
    p.add_argument("--uncertainties", default="UNKNOWN")
    p.add_argument("--next-step", default="UNKNOWN")
    p.add_argument("--baseline", default="UNKNOWN")
    p.add_argument("--cluster", default="")
    p.set_defaults(func=cmd_obs_start)

    p = sub.add_parser("obs-finish")
    p.add_argument("--episode-id", required=True)
    p.add_argument("--new-fact", default="false")
    p.add_argument("--contradicting", default="false")
    p.add_argument("--stale-corrected", default="false")
    p.add_argument("--quality-risk", default="false")
    p.add_argument("--path-changed", default="false")
    p.add_argument("--time-saved", default="false")
    p.add_argument("--no-incremental", default="false")
    p.add_argument("--effort-bucket", default="UNKNOWN",
                   choices=["<5", "5-15", "15-30", ">30", "UNKNOWN"])
    p.add_argument("--misuse-risk", default="UNKNOWN", choices=["NONE", "LOW", "MODERATE", "HIGH", "UNKNOWN"])
    p.add_argument("--misuse-type", default="")
    p.add_argument("--design-issue", default="false")
    p.add_argument("--post-next", default="UNKNOWN")
    p.add_argument("--notes", default="")
    p.add_argument("--synthetic", default="false")
    p.add_argument("--product-error", default="false")
    p.set_defaults(func=cmd_obs_finish)

    sub.add_parser("obs-list").set_defaults(func=cmd_obs_list)
    sub.add_parser("obs-report").set_defaults(func=cmd_obs_report)
    p = sub.add_parser("obs-export")
    p.add_argument("--csv", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_obs_export)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.out = Path(args.out)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
