"""Priority review helper for unresolved CUSIP mappings (Task B support).

This script is FACTS-ONLY. It never guesses a ticker and never auto-writes to
config/ticker_mappings.csv. It lists unresolved securities by two objective
priority signals:
  - holder count (how many tracked managers report it)
  - latest total value (sum of value across the latest report period)

It also reports whether config/portfolio.csv contains any tickers (P0), and
notes that portfolio tickers can only be mapped after human verification via
the curated CSV. Output: reports/unresolved_priority.md.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import connect, init_db


def load_portfolio_tickers(path: Path) -> list[str]:
    tickers: list[str] = []
    if not path.exists():
        return tickers
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            ticker = (row.get("ticker") or "").strip().upper()
            if ticker:
                tickers.append(ticker)
    return tickers


def main() -> int:
    parser = argparse.ArgumentParser(description="Unresolved mapping priority")
    parser.add_argument("--db", default=str(ROOT / "data" / "thirteenf.db"))
    parser.add_argument("--portfolio", default=str(ROOT / "config" / "portfolio.csv"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "unresolved_priority.md"))
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    conn = connect(args.db)
    init_db(conn)

    portfolio_tickers = load_portfolio_tickers(Path(args.portfolio))
    latest_period = conn.execute(
        "SELECT MAX(report_period) FROM filings WHERE ingest_status='OK'"
    ).fetchone()[0]

    by_holders = conn.execute(
        """
        SELECT s.cusip, MAX(s.issuer) AS issuer,
               COUNT(DISTINCT pc.manager_id) AS holders,
               SUM(pc.weight_now * 0) AS unused
        FROM position_changes pc
        JOIN securities s ON s.security_id = pc.security_id
        WHERE s.mapping_status = 'UNRESOLVED'
        GROUP BY s.cusip
        ORDER BY holders DESC, s.cusip
        LIMIT ?
        """,
        (args.top,),
    ).fetchall()

    by_value = conn.execute(
        """
        SELECT s.cusip, MAX(s.issuer) AS issuer,
               SUM(h.value) AS total_value,
               COUNT(DISTINCT h.manager_id) AS holders
        FROM holdings h
        JOIN securities s ON s.cusip = h.cusip
        WHERE s.mapping_status = 'UNRESOLVED'
          AND h.report_period = ?
        GROUP BY s.cusip
        ORDER BY total_value DESC
        LIMIT ?
        """,
        (latest_period or "", args.top),
    ).fetchall()

    total_unresolved = conn.execute(
        "SELECT COUNT(*) FROM securities WHERE mapping_status='UNRESOLVED'"
    ).fetchone()[0]
    total_securities = conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0]

    lines = [
        "# Unresolved CUSIP — Priority Review (facts only)",
        "",
        f"> Generated: {date.today().isoformat()}",
        f"> Unresolved securities: {total_unresolved} / {total_securities}",
        f"> Latest report period: {latest_period or 'N/A'}",
        "",
        "## P0 — My Portfolio",
        "",
    ]
    if portfolio_tickers:
        lines.append(
            f"- Portfolio tickers ({len(portfolio_tickers)}): "
            + ", ".join(portfolio_tickers)
        )
        lines.append(
            "- These can only be mapped after human verification; add verified "
            "rows to `config/ticker_mappings.csv`. No auto-mapping is performed."
        )
    else:
        lines.append("- `config/portfolio.csv` is empty; P0 has no securities.")
    lines += [
        "",
        "## By holder count (top)",
        "",
        "| CUSIP | Issuer | Holders |",
        "|---|---|---|",
    ]
    for cusip, issuer, holders, _ in by_holders:
        lines.append(f"| {cusip} | {issuer or ''} | {holders} |")
    lines += [
        "",
        "## By latest-period total value (top)",
        "",
        "| CUSIP | Issuer | Total value | Holders |",
        "|---|---|---|---|",
    ]
    for cusip, issuer, total_value, holders in by_value:
        lines.append(
            f"| {cusip} | {issuer or ''} | {total_value or 0} | {holders} |"
        )
    lines.append("")
    lines.append(
        "> This list is for human curation only. Every mapping must carry a "
        "source and be added to `config/ticker_mappings.csv` manually."
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    conn.close()
    print(
        f"unresolved={total_unresolved}/{total_securities} "
        f"portfolio_tickers={len(portfolio_tickers)}"
    )
    print(f"report={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

