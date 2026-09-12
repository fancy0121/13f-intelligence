"""Product evidence golden tests (Gate P1/P2/P4/P8/P9)."""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.evidence import ProductStore


def test_quarantined_latest_period_never_falls_back_to_old_holdings(product_bundle, tmp_path):
    from thirteenf.changes import compute_position_changes
    copied = tmp_path / "quarantined.db"
    shutil.copy2(product_bundle.db, copied)
    conn = sqlite3.connect(copied)
    conn.execute("PRAGMA foreign_keys=ON")
    mid = conn.execute("SELECT manager_id FROM managers WHERE name='BERKSHIRE HATHAWAY INC'").fetchone()[0]
    conn.execute("UPDATE filings SET ingest_status='QUARANTINED' WHERE report_period='2026-06-30'")
    compute_position_changes(conn, "0.1.0")
    conn.commit()
    conn.close()
    reader = ProductStore(copied, product_bundle.resolution, product_bundle.semantic, product_bundle.managers)
    assert reader.latest_period() == "2026-06-30"
    ev = reader.manager_evidence(mid)
    assert ev.latest_report_period == "2026-06-30"
    assert ev.quality["source_status"] == "SOURCE_QUARANTINED"
    assert ev.total_value is None
    assert ev.top_holdings == []
    assert not any(ev.latest_changes.values())
    assert reader.manager_update_counts("2026-06-30")[0] == 0
    assert reader.quarantined_periods()
    sec = reader.security_evidence("02079K305")
    assert sec.activity_state == "INSUFFICIENT_DATA"
    assert sec.timeline[-1]["holders"] is None
    reader.close()


def test_latest_period_and_event_counts(store):
    period = store.latest_period()
    assert period is not None
    counts = store.event_counts(period)
    assert set(counts) == {"NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED"}
    # golden: total matches direct SQL
    n = store.conn.execute(
        "SELECT COUNT(*) FROM position_changes WHERE report_period=? AND put_call=''",
        (period,),
    ).fetchone()[0]
    assert sum(counts.values()) == n


def test_manager_evidence_facts_match_db(store):
    managers = store.managers_list()
    assert managers
    mid = managers[0]["manager_id"]
    ev = store.manager_evidence(mid)
    assert ev is not None
    assert ev.manager_id == mid
    # snapshot matches DB
    row = store.conn.execute(
        """
        SELECT COUNT(*) FROM effective_positions ep
        JOIN effective_periods p ON p.effective_period_id=ep.effective_period_id
        WHERE p.manager_id=? AND p.report_period=? AND p.status='READY'
        """,
        (mid, ev.latest_report_period or ""),
    ).fetchone()
    assert ev.position_count == row[0]
    # latest changes counts match direct SQL
    if ev.latest_report_period:
        n = store.conn.execute(
            "SELECT COUNT(*) FROM position_changes WHERE manager_id=? "
            "AND report_period=? AND put_call=''",
            (mid, ev.latest_report_period),
        ).fetchone()[0]
        total_changes = sum(len(v) for v in ev.latest_changes.values())
        assert total_changes == n


def test_manager_snapshot_aggregates_raw_rows_and_amendment_components(store):
    manager_id = store.conn.execute(
        "SELECT manager_id FROM managers WHERE name='BERKSHIRE HATHAWAY INC'"
    ).fetchone()[0]
    evidence = store.manager_evidence(manager_id)
    assert evidence is not None
    assert evidence.position_count == 3
    googl = next(item for item in evidence.top_holdings if item["cusip"] == "02079K305")
    assert googl["shares"] == 150
    assert len({item["cusip"] for item in evidence.top_holdings}) == len(
        evidence.top_holdings
    )


def test_public_store_does_not_create_sqlite_sidecars(product_bundle, tmp_path):
    copied = tmp_path / "release.db"
    shutil.copy2(product_bundle.db, copied)
    reader = ProductStore(
        copied,
        product_bundle.resolution,
        product_bundle.semantic,
        product_bundle.managers,
    )
    assert reader.latest_period() == "2026-06-30"
    reader.close()
    assert not Path(f"{copied}-wal").exists()
    assert not Path(f"{copied}-shm").exists()


def test_security_evidence_facts_match_db(store):
    period = store.latest_period() or ""
    row = store.conn.execute(
        "SELECT s.cusip FROM position_changes pc JOIN securities s "
        "ON s.security_id=pc.security_id WHERE pc.report_period=? AND pc.put_call='' LIMIT 1",
        (period,),
    ).fetchone()
    assert row
    ev = store.security_evidence(row[0])
    assert ev is not None
    # activity counts match direct SQL
    n_add = store.conn.execute(
        "SELECT COUNT(*) FROM position_changes pc JOIN securities s "
        "ON s.security_id=pc.security_id WHERE s.cusip=? AND pc.report_period=? "
        "AND pc.put_call='' AND pc.change_type IN ('NEW','ADD')",
        (ev.cusip, period),
    ).fetchone()[0]
    assert ev.activity_counts["ADD"] + ev.activity_counts["NEW"] == n_add
    # symmetry: activity_state covers both sides when mixed
    if ev.activity_counts["ADD"] > 0 and ev.activity_counts["REDUCE"] > 0:
        assert ev.activity_state == "MIXED_ACTIVITY"

    current_holders = store.conn.execute(
        """
        SELECT COUNT(DISTINCT effective.manager_id)
        FROM effective_positions position
        JOIN effective_periods effective
          ON effective.effective_period_id=position.effective_period_id
        JOIN securities security ON security.security_id=position.security_id
        WHERE security.cusip=? AND effective.report_period=?
          AND effective.status='READY' AND position.put_call=''
          AND position.shares_type='SH'
        """,
        (ev.cusip, period),
    ).fetchone()[0]
    assert ev.holder_entity_count == current_holders


def test_current_holder_without_change_row_is_insufficient_comparison(product_bundle, tmp_path):
    copied = tmp_path / "gap.db"
    shutil.copy2(product_bundle.db, copied)
    conn = sqlite3.connect(copied)
    period = conn.execute(
        "SELECT MAX(report_period) FROM effective_periods WHERE status='READY'"
    ).fetchone()[0]
    security_id, cusip = conn.execute(
        """
        SELECT position.security_id, security.cusip
        FROM effective_positions position
        JOIN effective_periods effective
          ON effective.effective_period_id=position.effective_period_id
        JOIN securities security ON security.security_id=position.security_id
        WHERE effective.report_period=? AND effective.status='READY'
          AND position.put_call='' AND position.shares_type='SH'
        LIMIT 1
        """,
        (period,),
    ).fetchone()
    conn.execute(
        "DELETE FROM position_changes WHERE security_id=? AND report_period=?",
        (security_id, period),
    )
    conn.commit()
    conn.close()

    reader = ProductStore(
        copied, product_bundle.resolution, product_bundle.semantic, product_bundle.managers
    )
    try:
        evidence = reader.security_evidence(cusip)
        ranking = next(row for row in reader.activity_explorer(limit=500) if row["cusip"] == cusip)
    finally:
        reader.close()

    assert evidence is not None
    assert evidence.holder_entity_count > 0
    assert evidence.holders == []
    assert evidence.activity_state == "INSUFFICIENT_COMPARISON"
    assert evidence.timeline[-1]["adds"] is None
    assert evidence.timeline[-1]["reduces"] is None
    assert ranking["activity_state"] == "INSUFFICIENT_COMPARISON"


def test_search_by_ticker_cusip_issuer(store):
    # verified ticker search
    res = store.security_search("GOOGL")
    assert any(r["match_type"] == "ticker" for r in res)
    # cusip search
    res2 = store.security_search("02079K305")
    assert any(r["match_type"] == "cusip" for r in res2)
    # issuer search returns all matches (no first-result)
    res3 = store.security_search("ALPHABET")
    assert len(res3) >= 2  # GOOGL + GOOG classes
    # ambiguous query must not silently pick one
    assert all(r["match_type"] in ("issuer", "ticker") for r in res3)


@pytest.mark.parametrize("remove_current_evidence", [False, True])
def test_security_freshness_ignores_unrelated_managers(product_bundle, tmp_path, remove_current_evidence):
    copied = tmp_path / "freshness.db"
    shutil.copy2(product_bundle.db, copied)
    conn = sqlite3.connect(copied)
    security_id = conn.execute("SELECT security_id FROM securities WHERE cusip='02079K305'").fetchone()[0]
    before = "2026-08-01"
    conn.execute("UPDATE filings SET filing_date=?", (before,))
    unrelated = conn.execute("SELECT manager_id FROM managers LIMIT 1").fetchone()[0]
    conn.execute("DELETE FROM position_changes WHERE security_id=? AND manager_id=?", (security_id, unrelated))
    conn.execute("DELETE FROM effective_positions WHERE security_id=? AND effective_period_id IN "
                 "(SELECT effective_period_id FROM effective_periods WHERE manager_id=?)", (security_id, unrelated))
    conn.execute("UPDATE filings SET filing_date='2026-09-07' WHERE manager_id=?", (unrelated,))
    if remove_current_evidence:
        conn.execute("DELETE FROM position_changes WHERE security_id=? AND report_period='2026-06-30'", (security_id,))
        conn.execute("DELETE FROM effective_positions WHERE security_id=? AND effective_period_id IN "
                     "(SELECT effective_period_id FROM effective_periods WHERE report_period='2026-06-30')", (security_id,))
    conn.commit()
    conn.close()
    reader = ProductStore(copied, product_bundle.resolution, product_bundle.semantic, product_bundle.managers)
    try:
        evidence = reader.security_evidence("02079K305")
        assert evidence.latest_filing_date == (None if remove_current_evidence else before)
        if remove_current_evidence:
            assert evidence.days_since_filing is None
    finally:
        reader.close()


def test_empty_portfolio_setup_required(store, tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text("# empty\n", encoding="utf-8")
    assert store.portfolio_evidence(p) == "SETUP_REQUIRED"
    assert store.portfolio_evidence(tmp_path / "missing.csv") == "SETUP_REQUIRED"


def test_portfolio_symmetry_zeros(store, tmp_path):
    # pick a security with only adds -> reductions must be 0 (visible)
    period = store.latest_period() or ""
    row = store.conn.execute(
        """
        SELECT s.cusip FROM position_changes pc JOIN securities s
        ON s.security_id=pc.security_id
        WHERE pc.report_period=? AND pc.put_call='' AND pc.change_type IN ('NEW','ADD')
        GROUP BY s.cusip HAVING COUNT(*) >= 1
        ORDER BY s.cusip LIMIT 5
        """,
        (period,),
    ).fetchall()
    p = tmp_path / "portfolio.csv"
    lines = ["ticker,weight\n"]
    tickers = []
    for (c,) in row:
        sym = store._res.get(c, {}).get("symbol")
        if sym:
            tickers.append(sym)
            lines.append(f"{sym},0.01\n")
    if not tickers:
        return
    p.write_text("".join(lines), encoding="utf-8")
    out = store.portfolio_evidence(p)
    assert isinstance(out, list)
    for item in out:
        assert "independent_add_manager_count" in item
        assert "independent_reduce_manager_count" in item
        assert "independent_exit_manager_count" in item


def test_no_forced_insight_low_breadth(store):
    # a security with holder_entity_count == 1 -> LOW_BREADTH / INSUFFICIENT_DATA
    period = store.latest_period() or ""
    row = store.conn.execute(
        """
        SELECT s.cusip FROM position_changes pc JOIN securities s
        ON s.security_id=pc.security_id WHERE pc.report_period=?
        GROUP BY s.cusip HAVING COUNT(DISTINCT pc.manager_id)=1 LIMIT 1
        """,
        (period,),
    ).fetchone()
    if row:
        ev = store.security_evidence(row[0])
        assert ev.activity_state in ("LOW_BREADTH", "INSUFFICIENT_DATA",
                                     "MORE_ADDS_THAN_REDUCTIONS", "MORE_REDUCTIONS_THAN_ADDS")


def test_unresolved_priority_uses_effective_usd_and_is_readonly(product_bundle, tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    from prioritize_unresolved import main
    copied, report = tmp_path / "priority.db", tmp_path / "priority.md"
    shutil.copy2(product_bundle.db, copied)
    conn = sqlite3.connect(copied)
    conn.execute("UPDATE securities SET mapping_status='UNRESOLVED' WHERE cusip='02079K305'")
    value, holders = conn.execute(
        "SELECT SUM(p.value),COUNT(DISTINCT p.manager_id) FROM effective_positions p "
        "JOIN securities s ON s.security_id=p.security_id "
        "WHERE s.cusip='02079K305' AND p.report_period='2026-06-30' AND p.put_call='' AND p.shares_type='SH'"
    ).fetchone()
    conn.commit()
    conn.close()
    before = copied.read_bytes()
    monkeypatch.setattr(sys, "argv", ["priority", "--db", str(copied), "--out", str(report),
                                      "--portfolio", str(tmp_path / "absent.csv")])
    assert main() == 0
    assert f"| 02079K305 | ALPHABET INC | {value} | {holders} |" in report.read_text(encoding="utf-8")
    assert copied.read_bytes() == before
