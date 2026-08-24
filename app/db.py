"""Shared read-only DB helpers for the Streamlit UI."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from thirteenf.database import connect

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "thirteenf.db"


def db_conn() -> sqlite3.Connection:
    return connect(DB_PATH)


def db_ready() -> bool:
    return DB_PATH.exists()


def latest_period(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT MAX(report_period) FROM filings WHERE ingest_status='OK'"
    ).fetchone()
    return row[0] if row else None


def manager_coverage(conn: sqlite3.Connection, period: str) -> tuple[int, int]:
    total = conn.execute("SELECT COUNT(*) FROM managers").fetchone()[0]
    updated = conn.execute(
        "SELECT COUNT(DISTINCT manager_id) FROM filings "
        "WHERE report_period=? AND ingest_status='OK'",
        (period,),
    ).fetchone()[0]
    return updated, total


def quality_summary(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    return conn.execute(
        "SELECT event_type, severity, COUNT(*) FROM quality_events "
        "GROUP BY event_type, severity ORDER BY severity, event_type"
    ).fetchall()


def notables(
    conn: sqlite3.Connection,
    period: str,
    change_type: str,
    limit: int = 10,
) -> list[tuple]:
    return conn.execute(
        """
        SELECT s.ticker, s.cusip, pc.manager_id, m.name,
               pc.share_change_pct, pc.weight_change
        FROM position_changes pc
        JOIN securities s ON s.security_id = pc.security_id
        JOIN managers m ON m.manager_id = pc.manager_id
        WHERE pc.report_period=? AND pc.change_type=? AND pc.put_call=''
        ORDER BY ABS(COALESCE(pc.share_change_pct, 0)) DESC
        LIMIT ?
        """,
        (period, change_type, limit),
    ).fetchall()


def consensus_reversals(conn: sqlite3.Connection, limit: int = 10) -> list[tuple]:
    return conn.execute(
        """
        SELECT s.ticker, s.cusip, t.report_period, t.trend_label,
               t.trend_score
        FROM trends t
        JOIN securities s ON s.security_id = t.security_id
        WHERE t.trend_label='REVERSAL' AND t.put_call=''
        ORDER BY t.report_period DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def managers_list(conn: sqlite3.Connection) -> list[tuple]:
    return conn.execute(
        """
        SELECT manager_id, name, cik, strategy_type, scoring_status,
               signal_quality, methodology_version
        FROM managers ORDER BY name
        """
    ).fetchall()


def manager_summary(conn: sqlite3.Connection, manager_id: int) -> dict:
    m = conn.execute(
        """
        SELECT name, cik, strategy_type, scoring_status, signal_quality,
               methodology_version, notes
        FROM managers WHERE manager_id=?
        """,
        (manager_id,),
    ).fetchone()
    if not m:
        return {}
    return {
        "name": m[0],
        "cik": m[1],
        "strategy_type": m[2],
        "scoring_status": m[3],
        "signal_quality": m[4],
        "methodology_version": m[5],
        "notes": m[6],
    }


def manager_activity(conn: sqlite3.Connection, manager_id: int) -> dict:
    counts = conn.execute(
        """
        SELECT change_type, COUNT(*)
        FROM position_changes
        WHERE manager_id=? AND report_period=(
            SELECT MAX(report_period) FROM position_changes WHERE manager_id=?
        )
        GROUP BY change_type
        """,
        (manager_id, manager_id),
    ).fetchall()
    return {r[0]: r[1] for r in counts}


def manager_top_holdings(
    conn: sqlite3.Connection, manager_id: int, period: str, limit: int = 10
) -> list[tuple]:
    return conn.execute(
        """
        SELECT s.ticker, s.cusip, h.issuer, h.shares, h.value,
               h.portfolio_weight, h.put_call
        FROM holdings h
        JOIN securities s ON s.cusip = h.cusip
        JOIN filings f ON f.filing_id = h.filing_id
        WHERE f.manager_id=? AND f.report_period=?
          AND f.ingest_status='OK'
        ORDER BY h.value DESC
        LIMIT ?
        """,
        (manager_id, period, limit),
    ).fetchall()


def manager_history(
    conn: sqlite3.Connection, manager_id: int, limit: int = 12
) -> list[tuple]:
    return conn.execute(
        """
        SELECT report_period, COUNT(*) AS filings
        FROM filings
        WHERE manager_id=? AND ingest_status='OK'
        GROUP BY report_period ORDER BY report_period DESC LIMIT ?
        """,
        (manager_id, limit),
    ).fetchall()


def stock_lookup(conn: sqlite3.Connection, ticker: str) -> int | None:
    row = conn.execute(
        "SELECT security_id FROM securities WHERE UPPER(ticker)=UPPER(?) "
        "AND mapping_status != 'UNRESOLVED' LIMIT 1",
        (ticker,),
    ).fetchone()
    return row[0] if row else None


def stock_holders(conn: sqlite3.Connection, security_id: int, period: str) -> list[tuple]:
    return conn.execute(
        """
        SELECT m.name, m.scoring_status, pc.change_type, pc.share_change_pct,
               pc.weight_now, pc.weight_change
        FROM position_changes pc
        JOIN managers m ON m.manager_id = pc.manager_id
        WHERE pc.security_id=? AND pc.report_period=? AND pc.put_call=''
        ORDER BY m.name
        """,
        (security_id, period),
    ).fetchall()


def stock_consensus(conn: sqlite3.Connection, security_id: int) -> list[tuple]:
    return conn.execute(
        """
        SELECT report_period, consensus_score, manager_count,
               independent_strategy_count
        FROM consensus_scores
        WHERE security_id=? AND put_call=''
        ORDER BY report_period
        """,
        (security_id,),
    ).fetchall()


def stock_trends(conn: sqlite3.Connection, security_id: int) -> list[tuple]:
    return conn.execute(
        """
        SELECT horizon, trend_label, trend_score, report_period
        FROM trends
        WHERE security_id=? AND put_call=''
        ORDER BY horizon
        """,
        (security_id,),
    ).fetchall()


def unresolved_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM securities WHERE mapping_status='UNRESOLVED'"
    ).fetchone()[0]
