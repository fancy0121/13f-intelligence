from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.changes import compute_position_changes, compute_portfolio_weights
from thirteenf.consensus import compute_consensus
from thirteenf.database import (
    connect,
    ensure_security,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)
from thirteenf.manager_scoring import apply_scoring
from thirteenf.trends import compute_trends


class _Row:
    def __init__(self, ordinal, cusip, issuer, shares, value, put_call=""):
        self.row_ordinal = ordinal
        self.cusip = cusip
        self.name_of_issuer = issuer
        self.title_of_class = "COM"
        self.put_call = put_call
        self.shares = shares
        self.value = value


def _scoring(tmp_path) -> Path:
    p = tmp_path / "manager_scoring.yaml"
    p.write_text(
        """
methodology_version: "0.1.0"
tiers:
  HIGH: 1.0
  MEDIUM: 0.7
managers:
  M1:
    strategy_type: fundamental
    tier: HIGH
    rationale: test
  M2:
    strategy_type: activist
    tier: MEDIUM
    rationale: test
  M3:
    strategy_type: passive
    tier: NON_SIGNAL
    rationale: test
""",
        encoding="utf-8",
    )
    return p


def _seed(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    mid1 = upsert_manager(conn, name="M1", cik=1)
    mid2 = upsert_manager(conn, name="M2", cik=2)
    mid3 = upsert_manager(conn, name="M3", cik=3)
    apply_scoring(conn, _scoring(tmp_path), methodology_version="0.1.0")
    sid = ensure_security(
        conn,
        cusip="AAAA11111",
        ticker="AAA",
        issuer="AAA Inc",
        share_class="COM",
        mapping_status="VERIFIED",
        mapping_source="MANUAL_REVIEW",
        mapping_date="2026-08-24",
    )
    return conn, {"M1": mid1, "M2": mid2, "M3": mid3}, sid


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


def test_consensus_uses_only_approved_and_is_explainable(tmp_path):
    conn, mids, sid = _seed(tmp_path)
    # Q1: M1 and M2 both hold AAA; M3 (passive, NON_SIGNAL) also holds.
    for label, acc in (("M1", "Q1A"), ("M2", "Q1B"), ("M3", "Q1C")):
        _filing(conn, mids[label], "2026-03-31", acc, [_Row(1, "AAAA11111", "AAA Inc", 100, 1000)])
    # Q2: M1 adds, M2 reduces, M3 holds.
    _filing(conn, mids["M1"], "2026-06-30", "Q2A", [_Row(1, "AAAA11111", "AAA Inc", 200, 2000)])
    _filing(conn, mids["M2"], "2026-06-30", "Q2B", [_Row(1, "AAAA11111", "AAA Inc", 50, 500)])
    _filing(conn, mids["M3"], "2026-06-30", "Q2C", [_Row(1, "AAAA11111", "AAA Inc", 100, 1000)])
    compute_portfolio_weights(conn)
    compute_position_changes(conn, "0.1.0")

    n = compute_consensus(conn, methodology_version="0.1.0")
    assert n >= 1
    row = conn.execute(
        """
        SELECT manager_count, independent_strategy_count, raw_contributions,
               consensus_score
        FROM consensus_scores WHERE security_id=? AND report_period='2026-06-30'
        """,
        (sid,),
    ).fetchone()
    # M3 (NON_SIGNAL, weight 0) is excluded from manager_count.
    assert row[0] == 2
    assert row[1] == 2
    contribs = json.loads(row[2])
    assert len(contribs) == 2
    assert all("contribution" in c for c in contribs)
    # M1 adds (positive), M2 reduces (negative); score between -1 and 1.
    assert -1.0 <= row[3] <= 1.0
    conn.close()


def test_consensus_empty_without_approved(tmp_path):
    conn, mids, sid = _seed(tmp_path)
    # Reset scoring: no approvals.
    conn.execute("UPDATE managers SET scoring_status='NOT_APPROVED', signal_quality=NULL")
    conn.commit()
    _filing(conn, mids["M1"], "2026-06-30", "Q1", [_Row(1, "AAAA11111", "AAA Inc", 100, 1000)])
    compute_portfolio_weights(conn)
    compute_position_changes(conn, "0.1.0")
    n = compute_consensus(conn, methodology_version="0.1.0")
    assert n == 0
    conn.close()


def test_trend_insufficient_history_when_no_consensus(tmp_path):
    conn, mids, sid = _seed(tmp_path)
    conn.execute("UPDATE managers SET scoring_status='NOT_APPROVED', signal_quality=NULL")
    conn.commit()
    _filing(conn, mids["M1"], "2026-06-30", "Q1", [_Row(1, "AAAA11111", "AAA Inc", 100, 1000)])
    compute_portfolio_weights(conn)
    compute_position_changes(conn, "0.1.0")
    compute_consensus(conn, methodology_version="0.1.0")
    n = compute_trends(conn, methodology_version="0.1.0")
    assert n == 0
    conn.close()

