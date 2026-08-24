"""Weighted Consensus (Governed Interpretation Layer).

Only managers with scoring_status='APPROVED' participate. The score is
transparent: raw per-manager contributions are stored as JSON so every
component (manager weight, significance, change signal) is inspectable.

  consensus = sum(weight_m * significance_m * change_score_m)
            / sum(weight_m * significance_m)

Score range [-1, 1] in the DB; display normalization to [-100, 100] is a UI
concern only. No LLM, fully deterministic and versioned.
"""

from __future__ import annotations

import json
import math
import sqlite3


def _change_score(change_type: str, share_change_pct, divisor: float) -> float:
    if change_type in ("EXIT",):
        return -1.0
    if change_type in ("NEW",):
        return 1.0
    if change_type == "ADD":
        pct = share_change_pct if share_change_pct is not None else 0.0
        return math.tanh(max(pct, 0.0) / divisor)
    if change_type == "REDUCE":
        pct = share_change_pct if share_change_pct is not None else 0.0
        return -math.tanh(max(-pct, 0.0) / divisor)
    return 0.0


def compute_consensus(
    conn: sqlite3.Connection,
    *,
    methodology_version: str,
    change_scale_divisor: float = 0.5,
    significance_mode: str = "min_prev_now",
) -> int:
    """Compute weighted consensus per (security, put_call, report_period).

    Only APPROVED managers are considered. Returns row count inserted.
    """
    approved = conn.execute(
        """
        SELECT manager_id, name, signal_quality
        FROM managers
        WHERE scoring_status = 'APPROVED' AND signal_quality IS NOT NULL
        """
    ).fetchall()
    if not approved:
        conn.execute("DELETE FROM consensus_scores")
        conn.commit()
        return 0
    weights = {r[0]: float(r[2]) for r in approved}

    changes = conn.execute(
        """
        SELECT pc.manager_id, pc.security_id, pc.put_call, pc.report_period,
               pc.change_type, pc.share_change_pct,
               pc.weight_prev, pc.weight_now
        FROM position_changes pc
        """
    ).fetchall()

    # group by (security_id, put_call, report_period)
    groups: dict[tuple[int, str, str], list[dict]] = {}
    for manager_id, security_id, put_call, period, ctype, pct, wp, wn in changes:
        if manager_id not in weights:
            continue
        key = (security_id, put_call or "", period)
        groups.setdefault(key, []).append(
            {
                "manager_id": manager_id,
                "change_type": ctype,
                "share_change_pct": pct,
                "weight_prev": wp,
                "weight_now": wn,
            }
        )

    conn.execute("DELETE FROM consensus_scores")
    inserted = 0
    for (security_id, put_call, period), members in groups.items():
        contribs = []
        denom = 0.0
        numerator = 0.0
        strategy_types: set[str] = set()
        for m in members:
            w = weights[m["manager_id"]]
            sig_prev = m["weight_prev"] or 0.0
            sig_now = m["weight_now"] or 0.0
            if significance_mode == "min_prev_now":
                significance = min(sig_prev, sig_now)
            else:
                significance = sig_now
            if significance <= 0 or w <= 0:
                continue
            cs = _change_score(
                m["change_type"], m["share_change_pct"], change_scale_divisor
            )
            contribution = w * significance * cs
            contribs.append(
                {
                    "manager_id": m["manager_id"],
                    "weight": w,
                    "significance": significance,
                    "change_score": cs,
                    "contribution": contribution,
                }
            )
            numerator += contribution
            denom += w * significance
            stype = conn.execute(
                "SELECT strategy_type FROM managers WHERE manager_id=?",
                (m["manager_id"],),
            ).fetchone()
            if stype and stype[0]:
                strategy_types.add(stype[0])
        if denom <= 0:
            continue
        score = numerator / denom
        conn.execute(
            """
            INSERT INTO consensus_scores(
                security_id, report_period, put_call, manager_count,
                high_quality_manager_count, independent_strategy_count,
                raw_contributions, consensus_score, methodology_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                security_id,
                period,
                put_call,
                len(contribs),
                len(contribs),
                len(strategy_types),
                json.dumps(contribs, ensure_ascii=False),
                round(score, 6),
                methodology_version,
            ),
        )
        inserted += 1
    conn.commit()
    return inserted
