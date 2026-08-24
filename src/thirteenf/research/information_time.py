"""Information-time alignment for research observations.

Every research observation carries:
  report_period            - quarter end (NOT known at that date)
  filing_date              - date the effective filing became public
  information_available_date - filing_date (amendment-aware)

Outcome starts must never precede information_available_date.
"""

from __future__ import annotations

import sqlite3


def effective_filing_dates(conn: sqlite3.Connection) -> dict[tuple[int, str], str]:
    """Return {(manager_id, report_period): filing_date} for the EFFECTIVE
    filing per period. Effective = 13F-HR/A preferred (newest filing date wins)
    to mirror the analyze-layer semantics; this gives the actual public
    availability date of the information."""
    rows = conn.execute(
        """
        SELECT manager_id, report_period, filing_date,
               ROW_NUMBER() OVER (
                   PARTITION BY manager_id, report_period
                   ORDER BY is_amendment DESC, filing_date DESC, filing_id DESC
               ) AS rn
        FROM filings
        WHERE ingest_status='OK'
        """
    ).fetchall()
    return {
        (r[0], r[1]): r[2]
        for r in rows
        if r[3] == 1
    }

