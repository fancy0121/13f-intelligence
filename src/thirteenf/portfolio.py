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


def _methodology_version(conn: sqlite3.Connection) -> str | None:
    rows = conn.execute(
        """
        SELECT DISTINCT methodology_version FROM effective_periods
        WHERE status='READY' ORDER BY methodology_version
        """
    ).fetchall()
    if len(rows) != 1:
        return None
    return str(rows[0][0])


def _latest_period(
    conn: sqlite3.Connection,
    methodology_version: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT MAX(report_period) FROM effective_periods
        WHERE status='READY' AND methodology_version=?
        """,
        (methodology_version,),
    ).fetchone()
    return row[0] if row else None


def _trend_label(
    conn,
    security_id: int,
    horizon: str,
    methodology_version: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT trend_label FROM trends
        WHERE security_id=? AND horizon=? AND put_call=''
          AND shares_type='SH' AND methodology_version=?
        ORDER BY report_period DESC LIMIT 1
        """,
        (security_id, horizon, methodology_version),
    ).fetchone()
    return row[0] if row else None


def evidence_for_holding(
    conn: sqlite3.Connection,
    *,
    security_id: int,
    ticker: str,
    period: str,
    methodology_version: str,
) -> HoldingEvidence:
    tracked = conn.execute(
        """
        SELECT COUNT(DISTINCT effective.manager_id)
        FROM effective_positions position
        JOIN effective_periods effective
          ON effective.effective_period_id=position.effective_period_id
        WHERE position.security_id=? AND effective.report_period=?
          AND effective.status='READY' AND effective.methodology_version=?
          AND position.put_call='' AND position.shares_type='SH'
        """,
        (security_id, period, methodology_version),
    ).fetchone()[0]

    high_quality = conn.execute(
        """
        SELECT COUNT(DISTINCT effective.manager_id)
        FROM effective_positions position
        JOIN effective_periods effective
          ON effective.effective_period_id=position.effective_period_id
        JOIN managers m ON m.manager_id=effective.manager_id
        WHERE position.security_id=? AND effective.report_period=?
          AND effective.status='READY' AND effective.methodology_version=?
          AND position.put_call='' AND position.shares_type='SH'
          AND m.scoring_status='APPROVED'
        """,
        (security_id, period, methodology_version),
    ).fetchone()[0]

    consensus = conn.execute(
        """
        SELECT consensus_score FROM consensus_scores
        WHERE security_id=? AND report_period=? AND put_call=''
          AND shares_type='SH' AND methodology_version=?
        ORDER BY report_period DESC LIMIT 1
        """,
        (security_id, period, methodology_version),
    ).fetchone()
    consensus_score = consensus[0] if consensus else None

    notable_new = conn.execute(
        """
        SELECT COUNT(*) FROM position_changes
        WHERE security_id=? AND report_period=? AND change_type='NEW'
          AND put_call='' AND shares_type='SH' AND methodology_version=?
        """,
        (security_id, period, methodology_version),
    ).fetchone()[0]
    notable_exit = conn.execute(
        """
        SELECT COUNT(*) FROM position_changes
        WHERE security_id=? AND report_period=? AND change_type='EXIT'
          AND put_call='' AND shares_type='SH' AND methodology_version=?
        """,
        (security_id, period, methodology_version),
    ).fetchone()[0]

    t1 = _trend_label(conn, security_id, "1Q", methodology_version)
    t4 = _trend_label(conn, security_id, "4Q", methodology_version)
    t8 = _trend_label(conn, security_id, "8Q", methodology_version)

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
    methodology_version = _methodology_version(conn)
    period = (
        _latest_period(conn, methodology_version)
        if methodology_version is not None
        else None
    )
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
        if methodology_version is None or period is None:
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
                    evidence="INSUFFICIENT_EVIDENCE",
                )
            )
            continue
        results.append(
            evidence_for_holding(
                conn,
                security_id=row[0],
                ticker=h.ticker,
                period=period,
                methodology_version=methodology_version,
            )
        )
    return results
