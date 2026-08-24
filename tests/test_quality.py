from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import (
    add_quality_event,
    connect,
    init_db,
    upsert_filing,
    upsert_manager,
)
from thirteenf.quality import run_all


def test_quality_events_surface(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    mid = upsert_manager(conn, name="STALE", cik=1)
    upsert_filing(
        conn,
        manager_id=mid,
        report_period="2015-12-31",
        filing_date="2016-02-12",
        accession_number="OLD",
        form_type="13F-HR",
        is_amendment=False,
        source_url="https://x",
        raw_checksum="abc",
        raw_path="/raw",
        fetched_at_utc=None,
        ingest_status="OK",
    )
    counts = run_all(conn, "0.1.0")
    assert counts["stale_filings"] == 1
    n = conn.execute(
        "SELECT COUNT(*) FROM quality_events WHERE event_type='STALE_FILING'"
    ).fetchone()[0]
    assert n == 1
    # Rerun is idempotent (events cleared then re-created).
    counts2 = run_all(conn, "0.1.0")
    n2 = conn.execute(
        "SELECT COUNT(*) FROM quality_events WHERE event_type='STALE_FILING'"
    ).fetchone()[0]
    assert n2 == 1
    assert counts2["stale_filings"] == 1
    conn.close()

