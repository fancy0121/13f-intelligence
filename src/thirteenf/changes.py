"""Objective position-change engine (deterministic, no LLM).

Computes per (manager, security, put_call, shares_type, report_period):
  - portfolio weight (value / filing total value)
  - NEW / ADD / REDUCE / EXIT / UNCHANGED
  - shares_prev / shares_now / share_change / share_change_pct
  - weight_prev / weight_now / weight_change

All analytical comparisons consume effective_positions. Raw holdings remain
an immutable audit layer and are never selected directly here.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from thirteenf.effective import (
    load_effective_positions,
    rebuild_effective_positions,
)

CHANGE_TYPES = ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")


def compute_portfolio_weights(conn: sqlite3.Connection) -> int:
    """Fill holdings.portfolio_weight = value / sum(value) per filing.

    Only filings with ingest_status='OK' and at least one holding are used.
    Returns number of holdings updated.
    """
    cur = conn.execute(
        """
        UPDATE holdings
        SET portfolio_weight = (
            SELECT value * 1.0 / total.value_total
            FROM (
                SELECT filing_id, SUM(value) AS value_total
                FROM holdings
                WHERE value IS NOT NULL
                GROUP BY filing_id
            ) AS total
            WHERE total.filing_id = holdings.filing_id
        )
        WHERE holdings.value IS NOT NULL
        """
    )
    conn.commit()
    return cur.rowcount


def effective_filings(
    conn: sqlite3.Connection,
    methodology_version: str | None = None,
) -> list[tuple[int, str, int]]:
    """Return the selected BASE filing for each READY effective period."""

    params: tuple[object, ...] = ()
    version_filter = ""
    if methodology_version is not None:
        version_filter = " AND ep.methodology_version=?"
        params = (methodology_version,)
    rows = conn.execute(
        f"""
        SELECT ep.manager_id, ep.report_period, efc.filing_id
        FROM effective_periods ep
        JOIN effective_filing_components efc
          ON efc.effective_period_id=ep.effective_period_id
         AND efc.component_role='BASE'
        WHERE ep.status='READY'{version_filter}
        ORDER BY ep.manager_id, ep.report_period
        """,
        params,
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def classify(prev: dict | None, now: dict) -> str:
    if prev is None:
        return "NEW"
    if now.get("shares") is None or prev.get("shares") is None:
        # Present in both periods but shares unavailable: cannot classify.
        return "UNCHANGED"
    if now["shares"] > prev["shares"]:
        return "ADD"
    if now["shares"] < prev["shares"]:
        return "REDUCE"
    return "UNCHANGED"


def compute_position_changes(
    conn: sqlite3.Connection, methodology_version: str
) -> int:
    """Compute transitions from READY effective periods only."""

    rebuild_effective_positions(conn, methodology_version)
    periods = conn.execute(
        """
        SELECT manager_id, report_period, status
        FROM effective_periods
        WHERE methodology_version=?
        ORDER BY manager_id, report_period
        """,
        (methodology_version,),
    ).fetchall()
    by_manager: dict[int, list[tuple[str, str]]] = {}
    for manager_id, report_period, status in periods:
        by_manager.setdefault(manager_id, []).append((report_period, status))

    conn.execute(
        "DELETE FROM position_changes WHERE methodology_version=?",
        (methodology_version,),
    )
    inserted = 0
    for manager_id, manager_periods in by_manager.items():
        prev: dict[tuple[int, str, str], dict] | None = None
        prev_period: str | None = None
        seen_period = False
        comparison_blocked = False
        for report_period, status in manager_periods:
            if status != "READY":
                seen_period = True
                prev = None
                prev_period = None
                comparison_blocked = True
                continue
            positions = load_effective_positions(
                conn,
                manager_id,
                report_period,
                methodology_version,
            )
            now = {
                key: {
                    "security_id": position.security_id,
                    "put_call": position.put_call,
                    "shares_type": position.shares_type,
                    "shares": position.shares,
                    "weight": position.portfolio_weight,
                    "value": position.value,
                }
                for key, position in positions.items()
            }
            if not seen_period:
                # First period: everything is NEW, prev values are None.
                for key in sorted(now):
                    rec = now[key]
                    inserted += _insert_change(
                        conn,
                        manager_id=manager_id,
                        security_id=rec["security_id"],
                        put_call=rec["put_call"],
                        shares_type=rec["shares_type"],
                        report_period=report_period,
                        change_type="NEW",
                        shares_prev=None,
                        shares_now=rec["shares"],
                        share_change=None,
                        share_change_pct=None,
                        weight_prev=None,
                        weight_now=rec["weight"],
                        weight_change=None,
                        methodology_version=methodology_version,
                    )
            elif (
                comparison_blocked
                or prev is None
                or prev_period is None
                or not _is_next_quarter(prev_period, report_period)
            ):
                _record_missing_comparison(
                    conn,
                    manager_id=manager_id,
                    report_period=report_period,
                    methodology_version=methodology_version,
                )
            else:
                for key in sorted(set(prev) | set(now)):
                    p = prev.get(key)
                    n = now.get(key)
                    if p is None:
                        change_type = "NEW"
                    elif n is None:
                        change_type = "EXIT"
                    else:
                        change_type = classify(p, n)
                    shares_prev = p["shares"] if p else None
                    shares_now = n["shares"] if n else None
                    weight_prev = p["weight"] if p else None
                    weight_now = n["weight"] if n else None
                    share_change = None
                    share_change_pct = None
                    if shares_prev is not None and shares_now is not None:
                        share_change = shares_now - shares_prev
                        if shares_prev != 0:
                            share_change_pct = share_change / shares_prev
                    weight_change = None
                    if weight_prev is not None and weight_now is not None:
                        weight_change = weight_now - weight_prev
                    inserted += _insert_change(
                        conn,
                        manager_id=manager_id,
                        security_id=key[0],
                        put_call=key[1],
                        shares_type=key[2],
                        report_period=report_period,
                        change_type=change_type,
                        shares_prev=shares_prev,
                        shares_now=shares_now,
                        share_change=share_change,
                        share_change_pct=share_change_pct,
                        weight_prev=weight_prev,
                        weight_now=weight_now,
                        weight_change=weight_change,
                        methodology_version=methodology_version,
                    )
            seen_period = True
            prev = now
            prev_period = report_period
            comparison_blocked = False
    conn.commit()
    return inserted


def _is_next_quarter(previous: str, current: str) -> bool:
    previous_date = date.fromisoformat(previous)
    current_date = date.fromisoformat(current)
    previous_index = previous_date.year * 4 + (previous_date.month - 1) // 3
    current_index = current_date.year * 4 + (current_date.month - 1) // 3
    return current_index == previous_index + 1


def _record_missing_comparison(
    conn: sqlite3.Connection,
    *,
    manager_id: int,
    report_period: str,
    methodology_version: str,
) -> None:
    message = (
        "missing or incomplete prior effective quarter; "
        f"methodology={methodology_version}"
    )
    conn.execute(
        """
        INSERT INTO quality_events(
            event_type, manager_id, report_period, severity, message,
            created_at_utc
        )
        SELECT 'MISSING_HISTORICAL_COMPARISON', ?, ?, 'WARN', ?, datetime('now')
        WHERE NOT EXISTS (
            SELECT 1 FROM quality_events
            WHERE event_type='MISSING_HISTORICAL_COMPARISON'
              AND manager_id=? AND report_period=? AND message=?
        )
        """,
        (
            manager_id,
            report_period,
            message,
            manager_id,
            report_period,
            message,
        ),
    )


def _insert_change(conn, **kwargs) -> int:
    conn.execute(
        """
        INSERT INTO position_changes(
            manager_id, security_id, put_call, shares_type, report_period,
            change_type,
            shares_prev, shares_now, share_change, share_change_pct,
            weight_prev, weight_now, weight_change, methodology_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kwargs["manager_id"],
            kwargs["security_id"],
            kwargs["put_call"],
            kwargs["shares_type"],
            kwargs["report_period"],
            kwargs["change_type"],
            kwargs["shares_prev"],
            kwargs["shares_now"],
            kwargs["share_change"],
            kwargs["share_change_pct"],
            kwargs["weight_prev"],
            kwargs["weight_now"],
            kwargs["weight_change"],
            kwargs["methodology_version"],
        ),
    )
    return 1
