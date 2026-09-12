"""Run independent Gate 2 analytics checks and emit a human review packet."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.validation.gate2 import run_gate2
from thirteenf.validation.gate_context import GateBundle, build_gate_context
from thirteenf.validation.manual_baseline import verify_manual_baseline


_PACKET_FIELDS = (
    "transition_id",
    "manager_id",
    "manager_name",
    "prev_period",
    "report_period",
    "cusip",
    "put_call",
    "shares_type",
    "expected_change",
    "expected_shares_prev",
    "expected_shares_now",
    "expected_weight_prev",
    "expected_weight_now",
    "production_change",
    "production_shares_prev",
    "production_shares_now",
    "production_weight_prev",
    "production_weight_now",
    "raw_provenance",
    "human_result",
    "reviewer",
    "review_date",
    "methodology_version",
    "effective_version",
    "reviewer_notes",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "thirteenf.db"))
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "validation" / "current"),
    )
    parser.add_argument("--methodology-version", default="0.1.0")
    parser.add_argument("--quarantine-policy")
    parser.add_argument("--min-transitions", type=int, default=30)
    parser.add_argument("--min-managers", type=int, default=5)
    parser.add_argument("--emit-manual-packet")
    parser.add_argument("--manual-baseline")
    args = parser.parse_args(argv)

    bundle = GateBundle(
        raw_root=Path(args.raw_root),
        db_path=Path(args.db),
        methodology_version=args.methodology_version,
        quarantine_policy_path=args.quarantine_policy,
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        context = build_gate_context(bundle)
        effective_version = f"v3:{context.effective_fingerprint}"
        result = run_gate2(
            bundle,
            min_transitions=args.min_transitions,
            min_managers=args.min_managers,
            effective_version=effective_version,
        )
        if args.emit_manual_packet:
            _write_packet(Path(args.emit_manual_packet), result.review_rows)

        human_status = "NOT_REVIEWED"
        manual_errors: tuple[str, ...] = ()
        if args.manual_baseline:
            manual = verify_manual_baseline(
                args.manual_baseline,
                args.methodology_version,
                effective_version,
                min_transitions=args.min_transitions,
                min_managers=args.min_managers,
                expected_transition_ids={
                    row["transition_id"] for row in result.review_rows
                },
            )
            human_status = "PASS" if manual.passed else "FAIL"
            manual_errors = manual.errors
        releaseable = result.passed and human_status == "PASS"
        payload = {
            "automatic_status": "PASS" if result.passed else "FAIL",
            "human_status": human_status,
            "releaseable": releaseable,
            "context": asdict(context),
            "effective_version": effective_version,
            "checked_transitions": result.checked_transitions,
            "manager_ids": list(result.manager_ids),
            "period_pairs": [list(pair) for pair in result.period_pairs],
            "mismatches": list(result.mismatches),
            "quarantine": result.quarantine,
            "manual_errors": list(manual_errors),
            "manual_packet": args.emit_manual_packet,
        }
    except Exception as exc:  # fail closed at the CLI boundary
        payload = {
            "automatic_status": "FAIL",
            "human_status": "NOT_REVIEWED",
            "releaseable": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    (output_dir / "gate2.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# Gate 2 — Analytical Correctness / 分析正确性",
        "",
        f"- Automatic / 自动核验: **{payload['automatic_status']}**",
        f"- Human review / 人工复核: **{payload['human_status']}**",
        f"- Releaseable / 可发布: **{payload['releaseable']}**",
        (
            "- Transitions checked / 核验变化数: "
            f"**{payload.get('checked_transitions', 0)}**"
        ),
        f"- Managers / 机构数: **{len(payload.get('manager_ids', []))}**",
        f"- Mismatches / 不匹配: **{len(payload.get('mismatches', []))}**",
        "",
        "The authoritative detail is gate2.json. / 权威明细见 gate2.json。",
    ]
    if payload.get("error"):
        lines.extend(("", f"- Error / 错误: `{payload['error']}`"))
    if payload["human_status"] == "NOT_REVIEWED":
        lines.extend(
            (
                "",
                "`NOT_REVIEWED`: automated agreement is not human Gate 2 approval.",
                "`NOT_REVIEWED`：自动对账一致不等于人工 Gate 2 已批准。",
            )
        )
    (output_dir / "gate2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "automatic_status": payload["automatic_status"],
                "human_status": payload["human_status"],
                "releaseable": payload["releaseable"],
                "report": str(output_dir / "gate2.json"),
            },
            sort_keys=True,
        )
    )
    if payload["releaseable"]:
        return 0
    return 2 if payload["automatic_status"] == "PASS" else 1


def _write_packet(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=_PACKET_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
