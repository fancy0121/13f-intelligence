from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.changes import (
    classify,
    compute_portfolio_weights,
    compute_position_changes,
    effective_filings,
)
from thirteenf.database import (
    connect,
    ensure_security,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)


def _seed(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    mid = upsert_manager(conn, name="M", cik=1)
    sid_a = ensure_security(
        conn,
        cusip="AAAA11111",
        ticker="AAA",
        issuer="AAA Inc",
        share_class="COM",
        mapping_status="VERIFIED",
        mapping_source="MANUAL_REVIEW",
        mapping_date="2026-08-24",
    )
    sid_b = ensure_security(
        conn,
        cusip="BBBB22222",
        ticker="BBB",
        issuer="BBB Inc",
        share_class="COM",
        mapping_status="VERIFIED",
        mapping_source="MANUAL_REVIEW",
        mapping_date="2026-08-24",
    )
    return conn, mid, sid_a, sid_b


class _Row:
    def __init__(self, ordinal, cusip, issuer, shares, value, put_call=""):
        self.row_ordinal = ordinal
        self.cusip = cusip
        self.name_of_issuer = issuer
        self.title_of_class = "COM"
        self.put_call = put_call
        self.shares = shares
        self.value = value


def _filing(conn, mid, period, accession, rows):
    fid = upsert_filing(
        conn,
        manager_id=mid,
        report_period=period,
        filing_date="2026-08-14",
        accession_number=accession,
        form_type="13F-HR",
        is_amendment=False,
        source_url="https://x",
        raw_checksum="abc",
        raw_path="/raw",
        fetched_at_utc=None,
        ingest_status="OK",
    )
    replace_holdings(
        conn,
        filing_id=fid,
        manager_id=mid,
        report_period=period,
        rows=rows,
    )
    return fid


def test_classify_basic():
    assert classify(None, {"shares": 1}) == "NEW"
    assert classify({"shares": 1}, {"shares": 2}) == "ADD"
    assert classify({"shares": 2}, {"shares": 1}) == "REDUCE"
    assert classify({"shares": 1}, {"shares": 1}) == "UNCHANGED"


def test_portfolio_weight_and_changes(tmp_path):
    conn, mid, sid_a, sid_b = _seed(tmp_path)
    # Q1: only A, 300 shares / 3000 value.
    _filing(conn, mid, "2026-03-31", "Q1", [_Row(1, "AAAA11111", "AAA Inc", 300, 3000)])
    # Q2: A 100 shares / 1000 value + B 500 shares / 5000 value.
    _filing(
        conn,
        mid,
        "2026-06-30",
        "Q2",
        [
            _Row(1, "AAAA11111", "AAA Inc", 100, 1000),
            _Row(2, "BBBB22222", "BBB Inc", 500, 5000),
        ],
    )

    compute_portfolio_weights(conn)
    # Q1: A weight = 3000/3000 = 1.0 ; Q2: A=1000/6000=0.1667, B=0.8333
    q1_a = conn.execute(
        "SELECT portfolio_weight FROM holdings WHERE report_period='2026-03-31'"
    ).fetchone()[0]
    assert abs(q1_a - 1.0) < 1e-9

    n = compute_position_changes(conn, "0.1.0")
    assert n == 3  # Q1: A NEW; Q2: A REDUCE, B NEW
    row_a = conn.execute(
        """
        SELECT change_type, shares_prev, shares_now, share_change,
               share_change_pct, weight_prev, weight_now, weight_change
        FROM position_changes
        WHERE security_id=? AND report_period='2026-06-30'
        """,
        (sid_a,),
    ).fetchone()
    assert row_a[0] == "REDUCE"
    assert row_a[1] == 300
    assert row_a[2] == 100
    assert row_a[3] == -200
    assert abs(row_a[4] - (-200 / 300)) < 1e-9
    assert abs(row_a[5] - 1.0) < 1e-9
    assert abs(row_a[6] - (1000 / 6000)) < 1e-9
    assert row_a[7] < 0  # weight decreased while shares decreased

    row_b = conn.execute(
        """
        SELECT change_type, shares_prev, shares_now, weight_prev, weight_now
        FROM position_changes
        WHERE security_id=? AND report_period='2026-06-30'
        """,
        (sid_b,),
    ).fetchone()
    assert row_b[0] == "NEW"
    assert row_b[1] is None
    conn.close()


def test_shares_up_weight_down_is_not_conviction(tmp_path):
    """shares increase but portfolio weight decreases => REDUCE is NOT used;
    classification stays ADD, weight_change is negative (visible divergence)."""
    conn, mid, sid_a, _ = _seed(tmp_path)
    _filing(conn, mid, "2026-03-31", "Q1", [_Row(1, "AAAA11111", "AAA Inc", 100, 100)])
    _filing(
        conn,
        mid,
        "2026-06-30",
        "Q2",
        [
            _Row(1, "AAAA11111", "AAA Inc", 150, 150),
            _Row(2, "BBBB22222", "BBB Inc", 10, 1000),
        ],
    )
    compute_portfolio_weights(conn)
    compute_position_changes(conn, "0.1.0")
    row = conn.execute(
        """
        SELECT change_type, share_change, weight_change
        FROM position_changes WHERE security_id=?
        """,
        (sid_a,),
    ).fetchall()
    # Q1 NEW, Q2 ADD with weight decrease.
    q2 = [r for r in row if r[0] == "ADD"][0]
    assert q2[1] == 50
    assert q2[2] < 0
    conn.close()


def test_amendment_supersedes_original(tmp_path):
    conn, mid, sid_a, _ = _seed(tmp_path)
    _filing(conn, mid, "2026-06-30", "A1", [_Row(1, "AAAA11111", "AAA Inc", 100, 100)])
    fid_a = upsert_filing(
        conn,
        manager_id=mid,
        report_period="2026-06-30",
        filing_date="2026-08-20",
        accession_number="A2",
        form_type="13F-HR/A",
        is_amendment=True,
        source_url="https://x",
        raw_checksum="abc",
        raw_path="/raw",
        fetched_at_utc=None,
        ingest_status="OK",
    )
    replace_holdings(
        conn,
        filing_id=fid_a,
        manager_id=mid,
        report_period="2026-06-30",
        rows=[_Row(1, "AAAA11111", "AAA Inc", 200, 200)],
    )
    effective = effective_filings(conn)
    chosen = [e for e in effective if e[0] == mid and e[1] == "2026-06-30"]
    assert len(chosen) == 1
    assert chosen[0][2] == fid_a  # amendment chosen
    conn.close()

