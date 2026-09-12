"""Run independent Gate 1 raw-to-normalized reconciliation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.validation.gate1 import run_gate1
from thirteenf.validation.gate_context import GateBundle, build_gate_context


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
    parser.add_argument("--managers", type=int, default=5)
    parser.add_argument("--quarters", type=int, default=3)
    parser.add_argument("--rows-per-filing", type=int, default=10)
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
        result = run_gate1(
            bundle,
            managers=args.managers,
            quarters=args.quarters,
            rows_per_filing=args.rows_per_filing,
        )
        payload = {
            "status": "PASS" if result.passed else "FAIL",
            "releaseable": result.passed,
            "context": asdict(context),
            "checked_rows": result.checked_rows,
            "manager_ids": list(result.manager_ids),
            "sampled_filings": list(result.sampled_filings),
            "mismatches": list(result.mismatches),
            "quarantine": result.quarantine,
        }
    except Exception as exc:  # fail closed at the CLI boundary
        payload = {
            "status": "FAIL",
            "releaseable": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    (output_dir / "gate1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# Gate 1 — Data Correctness / 数据正确性",
        "",
        f"- Status / 状态: **{payload['status']}**",
        f"- Releaseable / 可发布: **{payload['releaseable']}**",
        f"- Rows checked / 对账行数: **{payload.get('checked_rows', 0)}**",
        f"- Managers / 机构数: **{len(payload.get('manager_ids', []))}**",
        f"- Mismatches / 不匹配: **{len(payload.get('mismatches', []))}**",
        "",
        "The authoritative detail is gate1.json. / 权威明细见 gate1.json。",
    ]
    if payload.get("error"):
        lines.extend(("", f"- Error / 错误: `{payload['error']}`"))
    (output_dir / "gate1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "releaseable": payload["releaseable"],
                "report": str(output_dir / "gate1.json"),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["releaseable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
