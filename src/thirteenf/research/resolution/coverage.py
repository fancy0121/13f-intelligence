"""Universe + coverage + bias computation for the resolution gates (offline)."""

from __future__ import annotations

import sqlite3

import pandas as pd

from thirteenf.research.experiments import load_observations
from thirteenf.research.splits import (
    COMMON_WINDOW_END,
    COMMON_WINDOW_START,
    manager_split,
    protocol_time_split,
    security_split,
)
from thirteenf.research.resolution.engine import is_verified_status


def _direction(change_type: str) -> int:
    if change_type in ("NEW", "ADD"):
        return 1
    if change_type in ("REDUCE", "EXIT"):
        return -1
    return 0


def persistence_observations(obs: pd.DataFrame, k: int) -> pd.DataFrame:
    """Rows where (manager, security) direction is same for k consecutive
    quarters including current. Mirrors experiments._persistence_eligible."""
    work = obs[
        ["manager_id", "security_id", "cusip", "report_period", "change_type"]
    ].copy()
    work["direction"] = work["change_type"].map(_direction)
    work = work.sort_values(["manager_id", "security_id", "report_period"])
    flags: list[bool] = []
    for _key, group in work.groupby(["manager_id", "security_id"]):
        dirs = group["direction"].tolist()
        for i in range(len(dirs)):
            d = dirs[i]
            if d == 0:
                flags.append(False)
                continue
            run = 0
            j = i
            while j >= 0 and dirs[j] == d:
                run += 1
                j -= 1
            flags.append(run >= k)
    work["persist"] = flags
    return work[work["persist"]]


def build_observation_frames(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    """Return {'O0': obs, 'O1_2Q': obs, 'O1_3Q': obs} within the common window
    with split parts and activity labels."""
    obs = load_observations(conn)
    obs = obs[
        obs["report_period"].between(COMMON_WINDOW_START, COMMON_WINDOW_END)
    ].copy()
    obs = obs[obs["info_date"] != ""]
    m_split = manager_split(conn)
    s_split = security_split(conn)
    obs["manager_part"] = obs["manager_id"].map(m_split)
    obs["security_part"] = obs["cusip"].map(s_split)
    periods = sorted(obs["report_period"].unique().tolist())
    dev_periods, holdout_periods = protocol_time_split(periods)
    obs["part"] = "OTHER"
    obs.loc[
        obs["report_period"].isin(dev_periods)
        & (obs["manager_part"] == "development")
        & (obs["security_part"] == "development"),
        "part",
    ] = "H0_dev"
    obs.loc[
        obs["report_period"].isin(holdout_periods)
        & (obs["manager_part"] == "development")
        & (obs["security_part"] == "development"),
        "part",
    ] = "H1_time_holdout"
    obs.loc[
        obs["report_period"].isin(dev_periods)
        & (obs["manager_part"] == "holdout")
        & (obs["security_part"] == "development"),
        "part",
    ] = "H2_manager_holdout"
    obs.loc[
        obs["report_period"].isin(dev_periods)
        & (obs["manager_part"] == "development")
        & (obs["security_part"] == "holdout"),
        "part",
    ] = "H3_security_holdout"
    obs.loc[
        obs["report_period"].isin(holdout_periods)
        & (obs["manager_part"] == "holdout")
        & (obs["security_part"] == "holdout"),
        "part",
    ] = "H4_combined"
    obs["activity"] = obs["change_type"].map(
        lambda c: "positive" if c in ("NEW", "ADD") else (
            "negative" if c in ("REDUCE", "EXIT") else "neutral"
        )
    )
    frames = {"O0": obs}
    frames["O1_2Q"] = persistence_observations(obs, 2)
    frames["O1_3Q"] = persistence_observations(obs, 3)
    return frames


def build_universe(conn: sqlite3.Connection) -> pd.DataFrame:
    """R0/R1/R2 unique CUSIPs with observation counts."""
    frames = build_observation_frames(conn)
    all_cusips = sorted(set().union(*(set(df["cusip"]) for df in frames.values())))
    uni = pd.DataFrame(index=all_cusips)
    for variant, df in frames.items():
        counts = df.groupby("cusip").size()
        uni[variant] = counts.reindex(uni.index).fillna(0).astype(int)
    uni = uni.reset_index().rename(columns={"index": "cusip"})
    uni["r0"] = uni["O0"] > 0
    uni["r1"] = uni["O1_2Q"] > 0
    uni["r2"] = uni["O1_3Q"] > 0
    uni["total_obs"] = uni["O0"]
    uni = uni.sort_values(["total_obs", "cusip"], ascending=[False, True]).reset_index(drop=True)
    return uni


def load_master(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def load_availability(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def compute_coverage(
    frames: dict[str, pd.DataFrame],
    master: pd.DataFrame,
    availability: pd.DataFrame | None,
) -> dict:
    """Compute frozen coverage gates. Returns a nested dict of metrics."""
    verified = set(master.loc[master["status"].map(is_verified_status), "cusip"])
    sym_of = dict(zip(master["cusip"], master["symbol"]))
    avail_start = {}
    if availability is not None and len(availability):
        avail_start = dict(zip(availability["symbol"], availability["first_trade_date"]))

    def covered(row) -> bool:
        if row["cusip"] not in verified:
            return False
        sym = sym_of.get(row["cusip"])
        start = avail_start.get(sym) if sym else None
        if not sym or not start:
            return False
        return str(start) <= str(row["info_date"])

    out: dict = {}
    for variant, df in frames.items():
        eligible_total = len(df)
        covered_ser = df.apply(covered, axis=1)
        covered_total = int(covered_ser.sum())
        out[variant] = {
            "eligible_observations": eligible_total,
            "resolved_observations": covered_total,
            "observation_coverage": round(covered_total / eligible_total * 100, 3) if eligible_total else None,
        }
        for part in ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined"):
            sub = df[df["part"] == part]
            if len(sub) == 0:
                out[variant][part] = {
                    "eligible": 0, "resolved": 0, "coverage": None,
                    "note": "INSUFFICIENT_SAMPLE",
                }
                continue
            cov = int(covered_ser.loc[sub.index].sum())
            out[variant][part] = {
                "eligible": len(sub),
                "resolved": cov,
                "coverage": round(cov / len(sub) * 100, 3),
            }
        # activity coverage
        pos = df[df["activity"] == "positive"]
        neg = df[df["activity"] == "negative"]
        pos_cov = int(covered_ser.loc[pos.index].sum()) if len(pos) else 0
        neg_cov = int(covered_ser.loc[neg.index].sum()) if len(neg) else 0
        out[variant]["positive_activity"] = {
            "eligible": len(pos),
            "resolved": pos_cov,
            "coverage": round(pos_cov / len(pos) * 100, 3) if len(pos) else None,
        }
        out[variant]["negative_activity"] = {
            "eligible": len(neg),
            "resolved": neg_cov,
            "coverage": round(neg_cov / len(neg) * 100, 3) if len(neg) else None,
        }
    # security-level coverage
    all_cusips = set().union(*(set(df["cusip"]) for df in frames.values()))
    out["security_level"] = {
        "eligible_securities": len(all_cusips),
        "resolved_securities": len(all_cusips & verified),
        "coverage": round(len(all_cusips & verified) / len(all_cusips) * 100, 3) if all_cusips else None,
    }
    return out


def gate_evaluation(coverage: dict) -> dict:
    """Mechanical gate check per frozen thresholds."""
    gates = {}
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        c = coverage[variant]
        overall = c["observation_coverage"]
        per_split_ok = all(
            (c[p].get("coverage") or 0) >= 85.0
            for p in ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined")
            if c[p].get("note") != "INSUFFICIENT_SAMPLE" and c[p].get("coverage") is not None
        )
        dev = c["H0_dev"].get("coverage")
        diff_ok = True
        for p in ("H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined"):
            hc = c[p].get("coverage")
            if dev is not None and hc is not None and abs(dev - hc) > 5.0:
                diff_ok = False
        pos = c["positive_activity"].get("coverage")
        neg = c["negative_activity"].get("coverage")
        directional_ok = pos is None or neg is None or abs((pos or 0) - (neg or 0)) <= 5.0
        gates[variant] = {
            "overall_coverage": overall,
            "overall_gate": overall is not None and overall >= 90.0,
            "per_split_gate": per_split_ok,
            "differential_gate": diff_ok,
            "directional_gate": directional_ok,
            "PASS": (
                overall is not None
                and overall >= 90.0
                and per_split_ok
                and diff_ok
                and directional_ok
            ),
        }
    # variant differential bias
    o0 = gates["O0"]["overall_coverage"] or 0
    o1 = gates["O1_2Q"]["overall_coverage"] or 0
    o2 = gates["O1_3Q"]["overall_coverage"] or 0
    variant_bias = (o1 - o0 > 5.0) or (o2 - o0 > 5.0)
    gates["variant_differential_bias"] = {
        "O0": o0, "O1_2Q": o1, "O1_3Q": o2,
        "VARIANT_MAPPING_BIAS": variant_bias,
    }
    return gates
