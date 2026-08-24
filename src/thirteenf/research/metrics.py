"""Research metrics: coverage, stability, variance, dominance (EXPERIMENTAL)."""

from __future__ import annotations

import pandas as pd


def coverage(signals: pd.DataFrame) -> dict:
    eligible = int(signals["eligible"].sum())
    signal_producing = int((signals["net_directional"].abs() > 0).sum()) if (
        "net_directional" in signals.columns
    ) else None
    if "net_weight_direction" in signals.columns:
        signal_producing = int((signals["net_weight_direction"].abs() > 0).sum())
    n_sec = signals["security_id"].nunique()
    n_q = signals["report_period"].nunique()
    return {
        "eligible": eligible,
        "signal_producing": signal_producing,
        "security_coverage": n_sec,
        "quarter_coverage": n_q,
        "insufficient_data_rate": 0.0,
    }


def sign_stability(signals: pd.DataFrame, score_col: str) -> dict:
    """Quarter-to-quarter sign stability of a score column."""
    work = signals.sort_values(["security_id", "report_period"])
    work["sign"] = work[score_col].apply(lambda x: 0 if pd.isna(x) or x == 0 else (1 if x > 0 else -1))
    prev_sign = work.groupby("security_id")["sign"].shift(1)
    pairs = work.dropna(subset=["sign"]).copy()
    pairs["prev_sign"] = prev_sign
    pairs = pairs.dropna(subset=["prev_sign"])
    if len(pairs) == 0:
        return {"stability": None, "reversal_rate": None, "n_pairs": 0}
    same = (pairs["sign"] == pairs["prev_sign"]).sum()
    return {
        "stability": float(same / len(pairs)),
        "reversal_rate": 1.0 - float(same / len(pairs)),
        "n_pairs": int(len(pairs)),
    }


def leave_one_manager_out(
    obs: pd.DataFrame,
    score_fn,
    score_col: str,
) -> dict:
    """Dominance: flip fraction when removing each manager."""
    managers = obs["manager_id"].unique()
    base = score_fn(obs)
    base_sign = set(
        base.loc[base[score_col] != 0, "security_id"].tolist()
    )
    flips = 0
    total = 0
    top_contrib: dict[int, int] = {}
    for m in managers:
        reduced = score_fn(obs[obs["manager_id"] != m])
        reduced_sign = set(
            reduced.loc[reduced[score_col] != 0, "security_id"].tolist()
        )
        # Compare only securities that produced a signal in either.
        common = base_sign | reduced_sign
        for sec in common:
            b = (
                base.loc[base["security_id"] == sec, score_col].iloc[0]
                if (base["security_id"] == sec).any()
                else 0
            )
            r = (
                reduced.loc[reduced["security_id"] == sec, score_col].iloc[0]
                if (reduced["security_id"] == sec).any()
                else 0
            )
            if b == 0 or r == 0:
                continue
            total += 1
            if (b > 0) != (r > 0):
                flips += 1
                top_contrib[m] = top_contrib.get(m, 0) + 1
    return {
        "flip_fraction": float(flips / total) if total else None,
        "n_comparisons": total,
        "top_flip_manager": max(top_contrib, key=top_contrib.get) if top_contrib else None,
        "top_flip_count": max(top_contrib.values()) if top_contrib else 0,
    }

