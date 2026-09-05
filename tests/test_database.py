from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import (
    SCHEMA_VERSION,
    add_quality_event,
    connect,
    connect_readonly,
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


def test_schema_models_raw_fields_and_effective_positions(tmp_path):
    conn = _conn(tmp_path)
    holding_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(holdings)")
    }
    assert {
        "ssh_prnamt_type",
        "investment_discretion",
        "other_manager",
    } <= holding_columns

    filing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(filings)")
    }
    assert {
        "accepted_at",
        "amendment_number",
        "amendment_type",
        "amendment_status",
        "cover_checksum",
        "cover_raw_path",
    } <= filing_columns

    effective_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(effective_positions)")
    }
    assert {
        "effective_period_id",
        "security_id",
        "put_call",
        "shares_type",
        "shares",
        "value",
        "portfolio_weight",
        "provenance_json",
    } <= effective_columns
    assert "shares_type" in {
        row[1] for row in conn.execute("PRAGMA table_info(position_changes)")
    }
    assert "shares_type" in {
        row[1] for row in conn.execute("PRAGMA table_info(consensus_scores)")
    }
    assert "shares_type" in {
        row[1] for row in conn.execute("PRAGMA table_info(trends)")
    }
    conn.close()


def test_readonly_connection_cannot_write(tmp_path):
    path = tmp_path / "readonly.db"
    writable = connect(path)
    init_db(writable)
    writable.close()

    readonly = connect_readonly(path, immutable=True)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        readonly.execute("CREATE TABLE forbidden(x)")
    readonly.close()


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
        ssh_prnamt_type = "SH"
        investment_discretion = "SOLE"
        other_manager = "7"

    replace_holdings(conn, filing_id=fid, manager_id=mid, report_period="2026-06-30", rows=[Row()])
    n1 = conn.execute("SELECT COUNT(*) FROM holdings WHERE filing_id=?", (fid,)).fetchone()[0]
    replace_holdings(conn, filing_id=fid, manager_id=mid, report_period="2026-06-30", rows=[Row()])
    n2 = conn.execute("SELECT COUNT(*) FROM holdings WHERE filing_id=?", (fid,)).fetchone()[0]
    assert n1 == 1
    assert n2 == 1
    raw_fields = conn.execute(
        """
        SELECT ssh_prnamt_type, investment_discretion, other_manager
        FROM holdings WHERE filing_id=?
        """,
        (fid,),
    ).fetchone()
    assert tuple(raw_fields) == ("SH", "SOLE", "7")
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
