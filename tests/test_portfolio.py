from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.changes import compute_position_changes
from thirteenf.database import (
    connect,
    ensure_security,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)
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


def test_cross_check_counts_current_ordinary_share_holders_only(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    security_id = ensure_security(
        conn,
        cusip="037833100",
        ticker="AAPL",
        issuer="Apple Inc.",
        share_class="COM",
        mapping_status="VERIFIED",
        mapping_source="MANUAL_REVIEW",
        mapping_date="2026-08-24",
    )

    class Row:
        row_ordinal = 1
        cusip = "037833100"
        name_of_issuer = "APPLE INC"
        title_of_class = "COM"
        ssh_prnamt_type = "SH"
        investment_discretion = "SOLE"
        other_manager = ""
        shares = 100
        value = 1000

        def __init__(self, put_call):
            self.put_call = put_call

    for index, put_call in enumerate(("", "CALL"), start=1):
        manager_id = upsert_manager(conn, name=f"M{index}", cik=index)
        filing_id = upsert_filing(
            conn,
            manager_id=manager_id,
            report_period="2026-06-30",
            filing_date="2026-08-14",
            accession_number=f"ACC{index}",
            form_type="13F-HR",
            is_amendment=False,
            source_url="https://www.sec.gov/test",
            raw_checksum=f"hash{index}",
            raw_path=f"raw/{index}",
            fetched_at_utc="2026-08-14T00:00:00Z",
            ingest_status="OK",
            accepted_at="2026-08-14T10:00:00Z",
        )
        replace_holdings(
            conn,
            filing_id=filing_id,
            manager_id=manager_id,
            report_period="2026-06-30",
            rows=[Row(put_call)],
        )
    compute_position_changes(conn, "0.1.0")

    portfolio = tmp_path / "portfolio.csv"
    portfolio.write_text("ticker,weight\nAAPL,0.25\n", encoding="utf-8")
    result = cross_check(conn, portfolio)[0]
    assert result.tracked_holders == 1
    assert security_id > 0
    conn.close()
