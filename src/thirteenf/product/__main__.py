"""Product harness CLI (v0.4).

python -m thirteenf.product manifest   - build task dev/holdout manifest
python -m thirteenf.product validate   - run dev/holdout tasks, write validation report
python -m thirteenf.product snapshot   - deterministic query snapshot (reproducibility)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.evidence import ProductStore
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
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.out = Path(args.out)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
