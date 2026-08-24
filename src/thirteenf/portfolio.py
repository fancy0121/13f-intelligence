"""My Portfolio cross-check (v0.1).

Reads config/portfolio.csv (ticker, weight) and produces evidence for each
holding:
  - tracked holder count (managers reporting the security)
  - high-quality holder count (APPROVED managers only)
  - weighted consensus (latest period, governed layer)
  - 1Q/4Q/8Q trends
  - notable NEW / EXIT in the latest period
  - evidence direction label

This module NEVER produces BUY / SELL recommendations.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PortfolioHolding:
    ticker: str
    weight: float | None


@dataclass(frozen=True)
class HoldingEvidence:
    ticker: str
    tracked_holders: int
    high_quality_holders: int
    consensus_score: float | None
    trend_1q: str | None
    trend_4q: str | None
    trend_8q: str | None
    notable_new: int
    notable_exit: int
    evidence: str


def load_portfolio(path: Path) -> list[PortfolioHolding]:
    holdings: list[PortfolioHolding] = []
    if not path.exists():
        return holdings
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            ticker = (row.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            weight_raw = (row.get("weight") or "").strip()
            weight = None
            if weight_raw:
                try:
                    weight = float(weight_raw)
                except ValueError:
                    weight = None
            holdings.append(PortfolioHolding(ticker=ticker, weight=weight))
    return holdings


def _latest_period(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT MAX(report_period) FROM filings WHERE ingest_status='OK'"
    ).fetchone()
    return row[0] if row else None


def _trend_label(conn, security_id: int, horizon: str) -> str | None:
    row = conn.execute(
        """
        SELECT trend_label FROM trends
        WHERE security_id=? AND horizon=?
        ORDER BY report_period DESC LIMIT 1
        """,
        (security_id, horizon),
    ).fetchone()
    return row[0] if row else None


def evidence_for_holding(
    conn: sqlite3.Connection,
    *,
    security_id: int,
    ticker: str,
    period: str,
) -> HoldingEvidence:
    tracked = conn.execute(
        """
        SELECT COUNT(DISTINCT pc.manager_id)
        FROM position_changes pc
        WHERE pc.security_id=? AND pc.report_period=?
        """,
        (security_id, period),
    ).fetchone()[0]

    high_quality = conn.execute(
        """
        SELECT COUNT(DISTINCT pc.manager_id)
        FROM position_changes pc
        JOIN managers m ON m.manager_id = pc.manager_id
        WHERE pc.security_id=? AND pc.report_period=?
          AND m.scoring_status='APPROVED'
        """,
        (security_id, period),
    ).fetchone()[0]

    consensus = conn.execute(
        """
        SELECT consensus_score FROM consensus_scores
        WHERE security_id=? AND report_period=? AND put_call=''
        ORDER BY report_period DESC LIMIT 1
        """,
        (security_id, period),
    ).fetchone()
    consensus_score = consensus[0] if consensus else None

    notable_new = conn.execute(
        """
        SELECT COUNT(*) FROM position_changes
        WHERE security_id=? AND report_period=? AND change_type='NEW'
        """,
        (security_id, period),
    ).fetchone()[0]
    notable_exit = conn.execute(
        """
        SELECT COUNT(*) FROM position_changes
        WHERE security_id=? AND report_period=? AND change_type='EXIT'
        """,
        (security_id, period),
    ).fetchone()[0]

    t1 = _trend_label(conn, security_id, "1Q")
    t4 = _trend_label(conn, security_id, "4Q")
    t8 = _trend_label(conn, security_id, "8Q")

    if consensus_score is None:
        evidence = "INSUFFICIENT_EVIDENCE"
    elif consensus_score > 0.1:
        evidence = "EVIDENCE_STRENGTHENS"
    elif consensus_score < -0.1:
        evidence = "EVIDENCE_WEAKENS"
    else:
        evidence = "NO_MEANINGFUL_CHANGE"

    return HoldingEvidence(
        ticker=ticker,
        tracked_holders=tracked,
        high_quality_holders=high_quality,
        consensus_score=consensus_score,
        trend_1q=t1,
        trend_4q=t4,
        trend_8q=t8,
        notable_new=notable_new,
        notable_exit=notable_exit,
        evidence=evidence,
    )


def cross_check(
    conn: sqlite3.Connection,
    portfolio_path: Path,
) -> list[HoldingEvidence]:
    holdings = load_portfolio(portfolio_path)
    period = _latest_period(conn)
    results: list[HoldingEvidence] = []
    for h in holdings:
        row = conn.execute(
            "SELECT security_id FROM securities WHERE ticker=? AND "
            "mapping_status != 'UNRESOLVED' LIMIT 1",
            (h.ticker,),
        ).fetchone()
        if row is None:
            results.append(
                HoldingEvidence(
                    ticker=h.ticker,
                    tracked_holders=0,
                    high_quality_holders=0,
                    consensus_score=None,
                    trend_1q=None,
                    trend_4q=None,
                    trend_8q=None,
                    notable_new=0,
                    notable_exit=0,
                    evidence="UNRESOLVED",
                )
            )
            continue
        results.append(
            evidence_for_holding(
                conn,
                security_id=row[0],
                ticker=h.ticker,
                period=period or "",
            )
        )
    return results

