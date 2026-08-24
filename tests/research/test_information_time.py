from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import (
    connect,
    init_db,
    upsert_filing,
    upsert_manager,
)
from thirteenf.research.information_time import effective_filing_dates


def test_effective_filing_date_prefers_amendment(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    mid = upsert_manager(conn, name="M", cik=1)
    upsert_filing(
        conn,
        manager_id=mid,
        report_period="2026-06-30",
        filing_date="2026-08-14",
        accession_number="A1",
        form_type="13F-HR",
        is_amendment=False,
        source_url="x",
        raw_checksum="c",
        raw_path="/r",
        fetched_at_utc=None,
        ingest_status="OK",
    )
    upsert_filing(
        conn,
        manager_id=mid,
        report_period="2026-06-30",
        filing_date="2026-08-20",
        accession_number="A2",
        form_type="13F-HR/A",
        is_amendment=True,
        source_url="x",
        raw_checksum="c",
        raw_path="/r",
        fetched_at_utc=None,
        ingest_status="OK",
    )
    dates = effective_filing_dates(conn)
    assert dates[(mid, "2026-06-30")] == "2026-08-20"
    conn.close()


def test_information_time_never_before_filing_date(tmp_path):
    """Research observations must use filing_date, not report_period."""
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    mid = upsert_manager(conn, name="M", cik=1)
    upsert_filing(
        conn,
        manager_id=mid,
        report_period="2026-06-30",
        filing_date="2026-08-14",
        accession_number="A1",
        form_type="13F-HR",
        is_amendment=False,
        source_url="x",
        raw_checksum="c",
        raw_path="/r",
        fetched_at_utc=None,
        ingest_status="OK",
    )
    dates = effective_filing_dates(conn)
    assert dates[(mid, "2026-06-30")] > "2026-06-30"
    conn.close()

