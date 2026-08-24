"""1Q / 4Q / 8Q trend labels (deterministic rules, no LLM).

Uses the objective change signal per security across consecutive report
periods. Because managers may file at different times, the trend is computed
from the consensus score series where available; if the governed layer is
empty (no APPROVED managers), trends are reported as INSUFFICIENT_HISTORY.
"""

from __future__ import annotations

import sqlite3


def _label(score: float, stable_abs: float) -> str:
    if score > stable_abs:
        return "STRENGTHENING"
    if score < -stable_abs:
        return "WEAKENING"
    return "STABLE"


def compute_trends(
    conn: sqlite3.Connection,
    *,
    methodology_version: str,
    windows: tuple[int, ...] = (1, 4, 8),
    stable_abs_threshold: float = 0.1,
) -> int:
    """Compute trends from consensus_scores series per security.

    Only approved-manager consensus data is used, so the trend is part of the
    Governed Interpretation Layer and honestly returns INSUFFICIENT_HISTORY
    when no governed data exists.
    """
    rows = conn.execute(
        """
        SELECT security_id, put_call, report_period, consensus_score
        FROM consensus_scores
        WHERE methodology_version = ?
        ORDER BY security_id, put_call, report_period
        """,
        (methodology_version,),
    ).fetchall()

    series: dict[tuple[int, str], list[tuple[str, float]]] = {}
    for security_id, put_call, period, score in rows:
        series.setdefault((security_id, put_call or ""), []).append((period, score))

    conn.execute(
        "DELETE FROM trends WHERE methodology_version = ?",
        (methodology_version,),
    )
    inserted = 0
    for (security_id, put_call), points in series.items():
        points.sort(key=lambda x: x[0])
        scores = [p[1] for p in points]
        for horizon in windows:
            if len(scores) < horizon:
                label = "INSUFFICIENT_HISTORY"
                trend_score = None
            else:
                window_scores = scores[-horizon:]
                # Reversal: first half and second half disagree in direction.
                mid = len(window_scores) // 2
                first = sum(window_scores[:mid]) / max(mid, 1)
                second = sum(window_scores[mid:]) / max(len(window_scores) - mid, 1)
                if (first > 0 > second) or (first < 0 < second):
                    label = "REVERSAL"
                else:
                    label = _label(sum(window_scores) / len(window_scores), stable_abs_threshold)
                trend_score = round(sum(window_scores) / len(window_scores), 6)
            conn.execute(
                """
                INSERT INTO trends(
                    security_id, report_period, put_call, horizon, trend_label,
                    trend_score, methodology_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    security_id,
                    points[-1][0],
                    put_call,
                    f"{horizon}Q",
                    label,
                    trend_score,
                    methodology_version,
                ),
            )
            inserted += 1
    conn.commit()
    return inserted

