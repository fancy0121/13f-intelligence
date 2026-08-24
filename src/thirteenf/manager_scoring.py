"""Governed manager methodology.

The Governed Interpretation Layer (weighted consensus, high-quality manager
count) only admits managers with scoring_status='APPROVED'. Unapproved
managers keep signal_quality=NULL and never receive a default neutral score.

Scoring is coarse-grained (HIGH/MEDIUM/LOW/NON_SIGNAL) and driven by
config/manager_scoring.yaml, which is versioned, documented and reviewable.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

TIERS = ("HIGH", "MEDIUM", "LOW", "NON_SIGNAL")


@dataclass(frozen=True)
class ManagerScore:
    label: str
    strategy_type: str
    tier: str | None
    rationale: str


def load_scoring(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def tier_weight(tier: str | None, scoring: dict) -> float:
    if not tier:
        return 0.0
    tiers = scoring.get("tiers", {})
    return float(tiers.get(tier, 0.0))


def apply_scoring(
    conn: sqlite3.Connection,
    scoring_path: Path,
    *,
    methodology_version: str,
) -> dict[str, int]:
    """Apply the governance file to the managers table.

    - APPROVED managers (tier present in the file) get their tier + weight.
    - All others are reset to scoring_status='NOT_APPROVED', signal_quality=NULL.
    This function NEVER invents scores; it only reflects the governance file.
    """
    scoring = load_scoring(scoring_path)
    managers = scoring.get("managers") or {}

    approved = 0
    not_approved = 0
    for label, config in managers.items():
        tier = (config or {}).get("tier")
        strategy_type = (config or {}).get("strategy_type", "")
        rationale = (config or {}).get("rationale", "")
        if tier not in TIERS:
            # Listed but not approved -> NOT_APPROVED.
            conn.execute(
                """
                UPDATE managers
                SET strategy_type=?,
                    signal_quality=NULL,
                    scoring_status='NOT_APPROVED',
                    methodology_version=?
                WHERE name=?
                """,
                (strategy_type, methodology_version, label),
            )
            not_approved += 1
            continue
        weight = tier_weight(tier, scoring)
        conn.execute(
            """
            UPDATE managers
            SET strategy_type=?,
                signal_quality=?,
                scoring_status='APPROVED',
                methodology_version=?
            WHERE name=?
            """,
            (strategy_type, weight, methodology_version, label),
        )
        approved += 1
    conn.commit()
    return {"approved": approved, "not_approved": not_approved}


def approved_managers(conn: sqlite3.Connection) -> list[tuple[int, str, float]]:
    """Return (manager_id, name, weight) for APPROVED managers only."""
    rows = conn.execute(
        """
        SELECT manager_id, name, signal_quality
        FROM managers
        WHERE scoring_status = 'APPROVED' AND signal_quality IS NOT NULL
        """
    ).fetchall()
    return [(r[0], r[1], float(r[2])) for r in rows]


def manager_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT scoring_status, COUNT(*) FROM managers GROUP BY scoring_status"
    ).fetchall()
    return {r[0]: r[1] for r in rows}
