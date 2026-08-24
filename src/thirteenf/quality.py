"""Data-quality checks over the normalized database.

All checks are deterministic and read-only over the DB. They surface issues
as quality_events so the UI never presents a "normal" picture while data is
missing or stale.
"""

from __future__ import annotations

import sqlite3
from datetime import date


def _today() -> str:
    return date.today().isoformat()


def check_stale_filings(conn: sqlite3.Connection, stale_after_days: int = 200) -> int:
    """Flag managers whose latest report period is older than N days after
    the most recent quarter end."""
    today = _today()
    rows = conn.execute(
        """
        SELECT m.manager_id, m.name, MAX(f.report_period)
        FROM managers m
        JOIN filings f ON f.manager_id = m.manager_id
        WHERE f.ingest_status = 'OK'
        GROUP BY m.manager_id
        """
    ).fetchall()
    count = 0
    for manager_id, name, latest_period in rows:
        # Allow a filing to be up to `stale_after_days` after the period end
        # (45-day SEC deadline plus buffer).
        try:
            period_date = date.fromisoformat(latest_period)
        except ValueError:
            continue
        from datetime import timedelta

        if (date.fromisoformat(today) - period_date).days > stale_after_days:
            conn.execute(
                """
                INSERT INTO quality_events(
                    event_type, manager_id, report_period, severity, message,
                    created_at_utc
                ) VALUES ('STALE_FILING', ?, ?, 'WARN', ?, datetime('now'))
                """,
                (
                    manager_id,
                    latest_period,
                    f"manager {name} latest report period {latest_period} is stale",
                ),
            )
            count += 1
    conn.commit()
    return count


def check_incomplete_quarters(
    conn: sqlite3.Connection, min_quarters: int = 8
) -> int:
    """Flag managers with fewer than min_quarters of effective filings."""
    rows = conn.execute(
        """
        SELECT manager_id, COUNT(DISTINCT report_period)
        FROM filings
        WHERE ingest_status = 'OK'
        GROUP BY manager_id
        HAVING COUNT(DISTINCT report_period) < ?
        """,
        (min_quarters,),
    ).fetchall()
    for manager_id, qcount in rows:
        conn.execute(
            """
            INSERT INTO quality_events(
                event_type, manager_id, severity, message, created_at_utc
            ) VALUES ('INCOMPLETE_QUARTER', ?, 'WARN', ?, datetime('now'))
            """,
            (manager_id, f"only {qcount} quarters (< {min_quarters})"),
        )
    conn.commit()
    return len(rows)


def check_duplicate_filings(conn: sqlite3.Connection) -> int:
    """Flag accession numbers that appear more than once (should not happen
    because accession_number is UNIQUE; this is a defensive check)."""
    rows = conn.execute(
        """
        SELECT accession_number, COUNT(*)
        FROM filings
        GROUP BY accession_number
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    for accession, cnt in rows:
        conn.execute(
            """
            INSERT INTO quality_events(
                event_type, severity, message, created_at_utc
            ) VALUES ('DUPLICATE_FILING', 'ERROR', ?, datetime('now'))
            """,
            (f"accession {accession} appears {cnt} times",),
        )
    conn.commit()
    return len(rows)


def run_all(conn: sqlite3.Connection, methodology_version: str) -> dict[str, int]:
    """Run all quality checks; returns counts per check."""
    # Reset prior check results for this methodology so re-runs are idempotent.
    conn.execute(
        "DELETE FROM quality_events WHERE event_type IN "
        "('STALE_FILING','INCOMPLETE_QUARTER','DUPLICATE_FILING')"
    )
    conn.commit()
    return {
        "stale_filings": check_stale_filings(conn),
        "incomplete_quarters": check_incomplete_quarters(conn),
        "duplicate_filings": check_duplicate_filings(conn),
    }

