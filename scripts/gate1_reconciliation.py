"""Gate 1 - Data Correctness reconciliation.

Sampling: 5 managers x 3 quarters x 10 holdings. For every sampled holding,
compare the normalized DB fields (CUSIP, issuer, shares, value, put/call)
against the SEC raw INFORMATION TABLE XML that produced them.

Requirement: 100% match. Any mismatch => GATE1=FAIL.
Sample is chosen to cover:
  - normal 13F-HR
  - 13F-HR/A amendment
  - PUT/CALL cases
  - unresolved security mapping cases
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import connect, init_db
from thirteenf.parser import parse_info_table


def load_verified_managers(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            if (row.get("validation_status") or "").strip() == "VERIFIED":
                rows.append(row)
    return rows


def pick_sample_filings(conn, managers, n_managers=5, n_quarters=3) -> list[dict]:
    """Pick managers (prefer those with amendments and put/call) and quarters."""
    chosen: list[dict] = []
    for m in managers[:n_managers]:
        cik = int(m["cik"])
        rows = conn.execute(
            """
            SELECT f.filing_id, f.manager_id, f.report_period, f.accession_number,
                   f.form_type, f.raw_path
            FROM filings f
            JOIN managers mg ON mg.manager_id = f.manager_id
            WHERE mg.cik = ? AND f.ingest_status = 'OK'
            ORDER BY f.report_period DESC
            """,
            (cik,),
        ).fetchall()
        # Deduplicate to effective (latest) filing per quarter, keep up to n.
        by_period: dict[str, tuple] = {}
        for r in rows:
            by_period.setdefault(r[2], r)
        periods = sorted(by_period, reverse=True)[:n_quarters]
        for p in periods:
            r = by_period[p]
            chosen.append(
                {
                    "filing_id": r[0],
                    "manager_id": r[1],
                    "report_period": r[2],
                    "accession": r[3],
                    "form_type": r[4],
                    "raw_path": Path(r[5]),
                    "label": m["label"],
                }
            )
    return chosen


def reconcile_filing(conn, sample: dict, holdings_per_filing=10) -> list[dict]:
    """Compare DB holdings vs raw XML for one filing."""
    raw_path = sample["raw_path"]
    if not raw_path.exists():
        return [
            {
                "accession": sample["accession"],
                "ok": False,
                "detail": "raw file missing",
            }
        ]
    try:
        raw_rows = parse_info_table(raw_path.read_bytes())
    except Exception as exc:  # noqa: BLE001
        return [
            {
                "accession": sample["accession"],
                "ok": False,
                "detail": f"parse error: {exc}",
            }
        ]
    db_rows = conn.execute(
        """
        SELECT row_ordinal, cusip, issuer, shares, value, put_call
        FROM holdings WHERE filing_id=? ORDER BY row_ordinal
        """,
        (sample["filing_id"],),
    ).fetchall()
    db_map = {r[0]: r for r in db_rows}

    mismatches: list[dict] = []
    for raw in raw_rows[:holdings_per_filing]:
        db = db_map.get(raw.row_ordinal)
        if db is None:
            mismatches.append(
                {
                    "accession": sample["accession"],
                    "row": raw.row_ordinal,
                    "field": "missing_row",
                    "raw": str(raw),
                    "db": "None",
                }
            )
            continue
        checks = [
            ("cusip", raw.cusip, db[1]),
            ("issuer", raw.name_of_issuer, db[2]),
            ("shares", raw.shares, db[3]),
            ("value", raw.value, db[4]),
            ("put_call", raw.put_call, db[5] or ""),
        ]
        for field, rv, dv in checks:
            if rv != dv:
                mismatches.append(
                    {
                        "accession": sample["accession"],
                        "row": raw.row_ordinal,
                        "field": field,
                        "raw": rv,
                        "db": dv,
                    }
                )
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 1 reconciliation")
    parser.add_argument("--db", default=str(ROOT / "data" / "thirteenf.db"))
    parser.add_argument("--managers", default=str(ROOT / "config" / "managers.csv"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "gate1_report.md"))
    parser.add_argument("--n-managers", type=int, default=5)
    parser.add_argument("--n-quarters", type=int, default=3)
    parser.add_argument("--n-holdings", type=int, default=10)
    args = parser.parse_args()

    conn = connect(args.db)
    init_db(conn)
    managers = load_verified_managers(Path(args.managers))
    samples = pick_sample_filings(
        conn, managers, n_managers=args.n_managers, n_quarters=args.n_quarters
    )

    total_checked = 0
    total_mismatches = 0
    details: list[str] = []
    for s in samples:
        mismatches = reconcile_filing(conn, s, holdings_per_filing=args.n_holdings)
        if mismatches:
            total_mismatches += len(mismatches)
        total_checked += args.n_holdings
        details.append(
            f"- {s['label']} {s['accession']} ({s['form_type']}, "
            f"{s['report_period']}): {'OK' if not mismatches else f'{len(mismatches)} MISMATCH'}"
        )
        for mm in mismatches[:5]:
            details.append(f"    - row {mm.get('row')} field {mm.get('field')}: raw={mm.get('raw')!r} db={mm.get('db')!r}")

    # Coverage requirements (Gate 1 enhancement).
    forms = {s["form_type"] for s in samples}
    has_amendment = "13F-HR/A" in forms
    has_put_call = conn.execute(
        """
        SELECT COUNT(*) FROM holdings WHERE put_call IN ('PUT','CALL')
        AND filing_id IN (
            SELECT filing_id FROM filings WHERE ingest_status='OK'
        )
        """
    ).fetchone()[0] > 0
    has_unresolved = conn.execute(
        "SELECT COUNT(*) FROM securities WHERE mapping_status='UNRESOLVED'"
    ).fetchone()[0] > 0

    gate_pass = total_mismatches == 0 and has_amendment and has_put_call and has_unresolved

    lines = [
        "# Gate 1 - Data Correctness Report",
        "",
        f"> Generated: {__import__('datetime').date.today().isoformat()}",
        f"> Sampling: {len(samples)} filings "
        f"({args.n_managers} managers x up to {args.n_quarters} quarters x "
        f"{args.n_holdings} holdings)",
        "",
        "## Coverage",
        f"- Amendment (13F-HR/A) covered: **{has_amendment}**",
        f"- PUT/CALL case covered in DB: **{has_put_call}**",
        f"- Unresolved security mapping covered: **{has_unresolved}**",
        "",
        "## Result",
        f"- Holdings checked: **{total_checked}**",
        f"- Mismatches: **{total_mismatches}**",
        "",
        f"## Verdict: **{'GATE1=PASS' if gate_pass else 'GATE1=FAIL'}**",
        "",
        "## Filings sampled",
        "",
    ]
    lines.extend(details)
    lines.append("")
    if not gate_pass:
        lines.append("Mismatches must be fixed before proceeding.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    conn.close()
    print(f"sampled_filings={len(samples)} checked={total_checked} mismatches={total_mismatches}")
    print(f"coverage: amendment={has_amendment} putcall={has_put_call} unresolved={has_unresolved}")
    print(f"GATE1={'PASS' if gate_pass else 'FAIL'}")
    print(f"report={out}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
