"""Objective position-change engine (deterministic, no LLM).

Computes per (manager, security, put_call, report_period):
  - portfolio weight (value / filing total value)
  - NEW / ADD / REDUCE / EXIT / UNCHANGED
  - shares_prev / shares_now / share_change / share_change_pct
  - weight_prev / weight_now / weight_change

Effective-filing semantics: for each (manager, report_period) the amendment
(13F-HR/A), when present, supersedes the original 13F-HR; the latest filing
date wins. Raw filings are never deleted or overwritten.
"""

from __future__ import annotations

import sqlite3

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


def effective_filings(conn: sqlite3.Connection) -> list[tuple[int, str, int]]:
    """Return (manager_id, report_period, filing_id) for the effective filing:
    prefer 13F-HR/A over 13F-HR for the same period; newest filing_date wins.
    """
    rows = conn.execute(
        """
        SELECT manager_id, report_period, filing_id,
               ROW_NUMBER() OVER (
                   PARTITION BY manager_id, report_period
                   ORDER BY is_amendment DESC, filing_date DESC, filing_id DESC
               ) AS rn
        FROM filings
        WHERE ingest_status = 'OK'
        """
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows if r[3] == 1]


def _holding_map(
    conn: sqlite3.Connection, filing_id: int
) -> dict[tuple[int, str], dict]:
    rows = conn.execute(
        """
        SELECT s.security_id, h.put_call, h.shares, h.portfolio_weight, h.value
        FROM holdings h
        JOIN securities s ON s.cusip = h.cusip
        WHERE h.filing_id = ?
        """,
        (filing_id,),
    ).fetchall()
    out: dict[tuple[int, str], dict] = {}
    for security_id, put_call, shares, weight, value in rows:
        key = (security_id, put_call or "")
        out[key] = {
            "security_id": security_id,
            "put_call": put_call or "",
            "shares": shares,
            "weight": weight,
            "value": value,
        }
    return out


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
    """Compute position_changes for all effective filing pairs, ordered by
    report period. Returns number of rows inserted.
    """
    effective = effective_filings(conn)
    by_manager: dict[int, list[tuple[str, int]]] = {}
    for manager_id, report_period, filing_id in effective:
        by_manager.setdefault(manager_id, []).append((report_period, filing_id))

    conn.execute("DELETE FROM position_changes")
    inserted = 0
    for manager_id, period_filings in by_manager.items():
        period_filings.sort(key=lambda x: x[0])
        prev: dict[tuple[int, str], dict] | None = None
        prev_period: str | None = None
        for report_period, filing_id in period_filings:
            now = _holding_map(conn, filing_id)
            if prev is None:
                # First period: everything is NEW, prev values are None.
                for key, rec in now.items():
                    inserted += _insert_change(
                        conn,
                        manager_id=manager_id,
                        security_id=rec["security_id"],
                        put_call=rec["put_call"],
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
            else:
                keys = set(prev) | set(now)
                for key in keys:
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
            prev = now
            prev_period = report_period
    conn.commit()
    return inserted


def _insert_change(conn, **kwargs) -> int:
    conn.execute(
        """
        INSERT INTO position_changes(
            manager_id, security_id, put_call, report_period, change_type,
            shares_prev, shares_now, share_change, share_change_pct,
            weight_prev, weight_now, weight_change, methodology_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kwargs["manager_id"],
            kwargs["security_id"],
            kwargs["put_call"],
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
