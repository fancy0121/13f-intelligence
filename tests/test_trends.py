from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import connect, init_db
from thirteenf.trends import compute_trends


def _consensus(conn, security_id, period, score, *, put_call="", shares_type="SH"):
    conn.execute(
        """
        INSERT INTO consensus_scores(
            security_id, report_period, put_call, shares_type, manager_count,
            high_quality_manager_count, independent_strategy_count,
            raw_contributions, consensus_score, methodology_version
        ) VALUES (?, ?, ?, ?, 1, 1, 1, '[]', ?, '0.1.0')
        """,
        (security_id, period, put_call, shares_type, score),
    )


def test_trends_keep_put_call_and_shares_type_separate(tmp_path):
    conn = connect(tmp_path / "trends.db")
    init_db(conn)
    periods = ("2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30")
    for period in periods:
        _consensus(conn, 1, period, 0.5)
        _consensus(conn, 1, period, -0.5, put_call="CALL")
        _consensus(conn, 1, period, 0.0, shares_type="PRN")
    conn.commit()

    assert compute_trends(
        conn,
        methodology_version="0.1.0",
        windows=(1, 4, 8),
    ) == 9
    rows = conn.execute(
        """
        SELECT put_call, shares_type, horizon, trend_label
        FROM trends ORDER BY put_call, shares_type, horizon
        """
    ).fetchall()
    labels = {(row[0], row[1], row[2]): row[3] for row in rows}
    assert labels[("", "SH", "4Q")] == "STRENGTHENING"
    assert labels[("CALL", "SH", "4Q")] == "WEAKENING"
    assert labels[("", "PRN", "4Q")] == "STABLE"
    assert labels[("", "SH", "8Q")] == "INSUFFICIENT_HISTORY"
    conn.close()


def test_trend_reversal_is_rule_based(tmp_path):
    conn = connect(tmp_path / "reversal.db")
    init_db(conn)
    for period, score in zip(
        ("2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"),
        (0.7, 0.4, -0.2, -0.6),
    ):
        _consensus(conn, 1, period, score)
    conn.commit()
    compute_trends(conn, methodology_version="0.1.0", windows=(4,))
    assert conn.execute("SELECT trend_label FROM trends").fetchone()[0] == "REVERSAL"
    conn.close()


def test_four_observations_with_a_gap_are_not_four_consecutive_quarters(tmp_path):
    conn = connect(tmp_path / "gap.db")
    init_db(conn)
    for period in ("2025-06-30", "2025-12-31", "2026-03-31", "2026-06-30"):
        _consensus(conn, 1, period, 0.5)
    conn.commit()
    compute_trends(conn, methodology_version="0.1.0", windows=(4,))
    assert tuple(conn.execute("SELECT trend_label, trend_score FROM trends").fetchone()) == ("INSUFFICIENT_HISTORY", None)
    conn.close()


def test_old_security_score_does_not_become_current_trend(tmp_path):
    conn = connect(tmp_path / "stale-trend.db")
    init_db(conn)
    _consensus(conn, 1, "2026-03-31", 0.5)
    _consensus(conn, 2, "2026-06-30", 0.5)
    conn.commit()
    compute_trends(conn, methodology_version="0.1.0", windows=(1,))
    assert tuple(conn.execute("SELECT report_period, trend_label, trend_score FROM trends WHERE security_id=1").fetchone()) == ("2026-06-30", "INSUFFICIENT_HISTORY", None)
    conn.close()
