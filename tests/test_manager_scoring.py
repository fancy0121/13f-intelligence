from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import connect, init_db, upsert_manager
from thirteenf.manager_scoring import (
    apply_scoring,
    approved_managers,
    manager_counts,
    tier_weight,
)


def _scoring_file(tmp_path, content: str) -> Path:
    p = tmp_path / "manager_scoring.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_default_is_not_approved_no_neutral_score(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    upsert_manager(conn, name="Berkshire Hathaway", cik=1)
    upsert_manager(conn, name="Citadel Advisors", cik=2)
    scoring = _scoring_file(
        tmp_path,
        """
methodology_version: "0.1.0"
tiers:
  HIGH: 1.0
  MEDIUM: 0.7
managers:
  Berkshire Hathaway:
    strategy_type: long_only_fundamental
    tier: HIGH
    rationale: test
""",
    )
    apply_scoring(conn, scoring, methodology_version="0.1.0")
    row = conn.execute(
        "SELECT signal_quality, scoring_status FROM managers WHERE name=?",
        ("Citadel Advisors",),
    ).fetchone()
    assert row[0] is None
    assert row[1] == "NOT_APPROVED"
    # Berkshire is listed+approved; Citadel (unlisted) stays out of the
    # governed layer.
    assert [a[1] for a in approved_managers(conn)] == ["Berkshire Hathaway"]
    conn.close()


def test_approved_managers_only(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    upsert_manager(conn, name="Berkshire Hathaway", cik=1)
    upsert_manager(conn, name="Citadel Advisors", cik=2)
    scoring = _scoring_file(
        tmp_path,
        """
methodology_version: "0.1.0"
tiers:
  HIGH: 1.0
managers:
  Berkshire Hathaway:
    strategy_type: long_only_fundamental
    tier: HIGH
    rationale: test
""",
    )
    apply_scoring(conn, scoring, methodology_version="0.1.0")
    approved = approved_managers(conn)
    assert len(approved) == 1
    assert approved[0][1] == "Berkshire Hathaway"
    assert approved[0][2] == 1.0
    assert manager_counts(conn) == {"APPROVED": 1, "NOT_APPROVED": 1}
    conn.close()


def test_tier_weight_lookup():
    scoring = {"tiers": {"HIGH": 1.0, "NON_SIGNAL": 0.0}}
    assert tier_weight("HIGH", scoring) == 1.0
    assert tier_weight("NON_SIGNAL", scoring) == 0.0
    assert tier_weight(None, scoring) == 0.0
