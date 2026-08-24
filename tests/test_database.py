from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import (
    SCHEMA_VERSION,
    add_quality_event,
    connect,
    ensure_security,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)


def _conn(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    return conn


def test_schema_and_upsert_idempotent(tmp_path):
    conn = _conn(tmp_path)
    mid = upsert_manager(conn, name="TEST", cik=123)
    mid2 = upsert_manager(conn, name="TEST2", cik=123)
    assert mid == mid2
    fid = upsert_filing(
        conn,
        manager_id=mid,
        report_period="2026-06-30",
        filing_date="2026-08-14",
        accession_number="ACC1",
        form_type="13F-HR",
        is_amendment=False,
        source_url="https://x",
        raw_checksum="abc",
        raw_path="/raw",
        fetched_at_utc="2026-08-14T00:00:00+00:00",
        ingest_status="OK",
    )
    fid2 = upsert_filing(
        conn,
        manager_id=mid,
        report_period="2026-06-30",
        filing_date="2026-08-14",
        accession_number="ACC1",
        form_type="13F-HR",
        is_amendment=False,
        source_url="https://x",
        raw_checksum="abc",
        raw_path="/raw",
        fetched_at_utc="2026-08-14T00:00:00+00:00",
        ingest_status="OK",
    )
    assert fid == fid2
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == SCHEMA_VERSION
    conn.close()


def test_holdings_replace_is_idempotent(tmp_path):
    conn = _conn(tmp_path)
    mid = upsert_manager(conn, name="TEST", cik=123)
    fid = upsert_filing(
        conn,
        manager_id=mid,
        report_period="2026-06-30",
        filing_date="2026-08-14",
        accession_number="ACC1",
        form_type="13F-HR",
        is_amendment=False,
        source_url="https://x",
        raw_checksum="abc",
        raw_path="/raw",
        fetched_at_utc=None,
        ingest_status="OK",
    )

    class Row:
        row_ordinal = 1
        cusip = "037833100"
        name_of_issuer = "APPLE INC"
        title_of_class = "COM"
        put_call = ""
        shares = 100
        value = 1000

    replace_holdings(conn, filing_id=fid, manager_id=mid, report_period="2026-06-30", rows=[Row()])
    n1 = conn.execute("SELECT COUNT(*) FROM holdings WHERE filing_id=?", (fid,)).fetchone()[0]
    replace_holdings(conn, filing_id=fid, manager_id=mid, report_period="2026-06-30", rows=[Row()])
    n2 = conn.execute("SELECT COUNT(*) FROM holdings WHERE filing_id=?", (fid,)).fetchone()[0]
    assert n1 == 1
    assert n2 == 1
    conn.close()


def test_security_and_quality_event(tmp_path):
    conn = _conn(tmp_path)
    sid = ensure_security(
        conn,
        cusip="037833100",
        ticker="AAPL",
        issuer="Apple Inc.",
        share_class="COM",
        mapping_status="VERIFIED",
        mapping_source="MANUAL_REVIEW",
        mapping_date="2026-08-24",
    )
    sid2 = ensure_security(
        conn,
        cusip="037833100",
        ticker=None,
        issuer=None,
        share_class=None,
        mapping_status="UNRESOLVED",
        mapping_source="",
        mapping_date="2026-08-24",
    )
    assert sid == sid2
    add_quality_event(
        conn,
        event_type="UNRESOLVED_CUSIP",
        severity="WARN",
        message="test",
    )
    n = conn.execute("SELECT COUNT(*) FROM quality_events").fetchone()[0]
    assert n == 1
    conn.close()

