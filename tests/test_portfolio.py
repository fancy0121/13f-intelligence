from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import connect, ensure_security, init_db, upsert_manager
from thirteenf.portfolio import cross_check, load_portfolio


def test_load_portfolio_parses_csv(tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text("ticker,weight\nAAPL,0.25\nMSFT,\n", encoding="utf-8")
    holdings = load_portfolio(p)
    assert len(holdings) == 2
    assert holdings[0].ticker == "AAPL"
    assert holdings[0].weight == 0.25
    assert holdings[1].weight is None


def test_cross_check_unresolved_ticker(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    upsert_manager(conn, name="M", cik=1)
    p = tmp_path / "portfolio.csv"
    p.write_text("ticker,weight\nZZZZ,0.1\n", encoding="utf-8")
    results = cross_check(conn, p)
    assert len(results) == 1
    assert results[0].evidence == "UNRESOLVED"
    assert results[0].tracked_holders == 0
    conn.close()


def test_cross_check_tracked_holders(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    upsert_manager(conn, name="M", cik=1)
    ensure_security(
        conn,
        cusip="037833100",
        ticker="AAPL",
        issuer="Apple Inc.",
        share_class="COM",
        mapping_status="VERIFIED",
        mapping_source="MANUAL_REVIEW",
        mapping_date="2026-08-24",
    )
    p = tmp_path / "portfolio.csv"
    p.write_text("ticker,weight\nAAPL,0.25\n", encoding="utf-8")
    results = cross_check(conn, p)
    assert results[0].ticker == "AAPL"
    assert results[0].evidence == "INSUFFICIENT_EVIDENCE"
    conn.close()

