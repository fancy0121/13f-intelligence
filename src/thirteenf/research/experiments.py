"""Experiment family A0-A4 (EXPERIMENTAL).

All functions read position_changes / holdings / securities / managers from
the FACT LAYER and return DataFrames. No writes to production tables.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from thirteenf.research.information_time import effective_filing_dates


def load_observations(conn: sqlite3.Connection) -> pd.DataFrame:
    """Position changes (put_call='') joined with security + manager + info date.

    Columns: security_id, cusip, manager_id, report_period, change_type,
    shares_prev, shares_now, weight_prev, weight_now, weight_change,
    info_date.
    """
    df = pd.read_sql_query(
        """
        SELECT pc.security_id, s.cusip, pc.manager_id, pc.report_period,
               pc.change_type, pc.shares_prev, pc.shares_now,
               pc.weight_prev, pc.weight_now, pc.weight_change
        FROM position_changes pc
        JOIN securities s ON s.security_id = pc.security_id
        WHERE pc.put_call = ''
        """,
        conn,
    )
    dates = effective_filing_dates(conn)
    df["info_date"] = df.apply(
        lambda r: dates.get((int(r["manager_id"]), r["report_period"]), ""),
        axis=1,
    )
    return df


def a0_signals(obs: pd.DataFrame) -> pd.DataFrame:
    """A0: equal-weight action counts + net directional count per
    (security_id, report_period)."""
    grouped = obs.groupby(["security_id", "cusip", "report_period"])
    out = grouped.size().rename("eligible").reset_index()
    counts = obs.groupby(["security_id", "report_period", "change_type"]).size()
    counts = counts.unstack(fill_value=0).reset_index()
    out = out.merge(counts, on=["security_id", "report_period"], how="left")
    for col in ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED"):
        if col not in out.columns:
            out[col] = 0
        out[col] = out[col].fillna(0).astype(int)
    out["net_directional"] = (out["NEW"] + out["ADD"]) - (out["REDUCE"] + out["EXIT"])
    return out


def _direction(change_type: str) -> int:
    if change_type in ("NEW", "ADD"):
        return 1
    if change_type in ("REDUCE", "EXIT"):
        return -1
    return 0


def _persistence_eligible(obs: pd.DataFrame, k: int) -> pd.DataFrame:
    """Mark observations where the (manager, security) direction is the same
    for k consecutive quarters (including current)."""
    work = obs[
        ["manager_id", "security_id", "cusip", "report_period", "change_type"]
    ].copy()
    work["direction"] = work["change_type"].map(_direction)
    work = work.sort_values(["manager_id", "security_id", "report_period"])
    work["persist"] = False
    for _key, group in work.groupby(["manager_id", "security_id"]):
        idx = group.index
        dirs = group["direction"].tolist()
        flags: list[bool] = []
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
        work.loc[idx, "persist"] = flags
    return work[work["persist"]]


def a1_signals(obs: pd.DataFrame, k: int = 2) -> pd.DataFrame:
    """A1: persistence filter on top of A0 (k consecutive same-direction)."""
    kept = _persistence_eligible(obs, k)
    return a0_signals(kept)


def a2_signals(obs: pd.DataFrame) -> pd.DataFrame:
    """A2: weight-direction classification + net weight-direction count."""
    work = obs.copy()

    def _weight_dir(row) -> str:
        ct = row["change_type"]
        if ct == "EXIT":
            return "EXIT"
        if ct == "NEW":
            return "NEW_WEIGHT" if pd.notna(row["weight_now"]) else "NEW_NO_WEIGHT"
        if ct in ("ADD", "REDUCE"):
            sp = row["shares_prev"]
            sn = row["shares_now"]
            wp = row["weight_prev"]
            wn = row["weight_now"]
            if pd.isna(sp) or pd.isna(sn) or pd.isna(wp) or pd.isna(wn):
                return "INCOMPLETE"
            if sn > sp and wn > wp:
                return "UP_UP"
            if sn > sp and wn < wp:
                return "UP_DOWN"
            if sn < sp and wn < wp:
                return "DOWN_DOWN"
            if sn < sp and wn > wp:
                return "DOWN_UP"
            return "UNCHANGED"
        return "UNCHANGED"

    work["weight_dir"] = work.apply(_weight_dir, axis=1)
    grouped = work.groupby(["security_id", "cusip", "report_period"])
    out = grouped.size().rename("eligible").reset_index()
    cats = work.groupby(["security_id", "report_period", "weight_dir"]).size()
    cats = cats.unstack(fill_value=0).reset_index()
    out = out.merge(cats, on=["security_id", "report_period"], how="left")
    for col in ("UP_UP", "UP_DOWN", "DOWN_DOWN", "DOWN_UP", "NEW_WEIGHT", "EXIT"):
        if col not in out.columns:
            out[col] = 0
        out[col] = out[col].fillna(0).astype(int)
    out["net_weight_direction"] = (
        out["UP_UP"] + out["NEW_WEIGHT"] - (out["DOWN_DOWN"] + out["EXIT"])
    )
    out["divergence_rate"] = (
        (out["UP_DOWN"] + out["DOWN_UP"]) / out["eligible"].replace(0, pd.NA)
    )
    return out


def manager_characteristics(conn: sqlite3.Connection) -> pd.DataFrame:
    """Data-driven manager characteristics from the FACT LAYER (no subjective
    scores)."""
    rows = conn.execute(
        """
        SELECT m.manager_id, m.name, m.cik,
               COUNT(DISTINCT f.report_period) AS filing_continuity,
               AVG(h.top10_share) AS avg_concentration,
               AVG(h.position_count) AS avg_position_count
        FROM managers m
        JOIN filings f ON f.manager_id = m.manager_id AND f.ingest_status='OK'
        LEFT JOIN (
            SELECT filing_id,
                   SUM(CASE WHEN rn <= 10 THEN value ELSE 0 END) * 1.0 /
                       NULLIF(SUM(value), 0) AS top10_share,
                   COUNT(*) AS position_count
            FROM (
                SELECT filing_id, value,
                       ROW_NUMBER() OVER (
                           PARTITION BY filing_id ORDER BY value DESC
                       ) AS rn
                FROM holdings
                WHERE put_call = ''
            )
            GROUP BY filing_id
        ) h ON h.filing_id = f.filing_id
        GROUP BY m.manager_id
        """
    ).fetchall()
    df = pd.DataFrame(
        rows,
        columns=[
            "manager_id",
            "name",
            "cik",
            "filing_continuity",
            "avg_concentration",
            "avg_position_count",
        ],
    )
    # options proxy: share of put/call holdings across all filings
    opt = conn.execute(
        """
        SELECT manager_id,
               SUM(CASE WHEN put_call != '' THEN 1 ELSE 0 END) * 1.0 /
                   NULLIF(COUNT(*), 0) AS options_proxy
        FROM holdings GROUP BY manager_id
        """
    ).fetchall()
    opt_df = pd.DataFrame(opt, columns=["manager_id", "options_proxy"])
    df = df.merge(opt_df, on="manager_id", how="left")
    return df


def bucket_managers(chars: pd.DataFrame, feature: str, n_buckets: int = 3) -> dict[int, str]:
    """Deterministic quantile buckets for a numeric manager feature.
    Returns {manager_id: 'LOW'|'MEDIUM'|'HIGH'} (or fewer buckets if ties).
    Bucketing is based on metadata only - not on outcomes."""
    series = chars.set_index("manager_id")[feature].dropna()
    if series.empty:
        return {}
    ranks = series.rank(method="first", pct=True)
    out: dict[int, str] = {}
    for mid, pct in ranks.items():
        if pct <= 1 / n_buckets:
            bucket = "LOW"
        elif pct <= 2 / n_buckets:
            bucket = "MEDIUM"
        else:
            bucket = "HIGH"
        out[int(mid)] = bucket
    return out


def a3_stratified(
    obs: pd.DataFrame,
    chars: pd.DataFrame,
    feature: str = "filing_continuity",
    score_fn=a2_signals,
    score_col: str = "net_weight_direction",
) -> dict[str, pd.DataFrame]:
    """A3: run the reference signal function within each manager-characteristic
    bucket. Returns {bucket: signals_df}. No weighted 'smart score' is built."""
    buckets = bucket_managers(chars, feature)
    out: dict[str, pd.DataFrame] = {}
    for bucket in ("LOW", "MEDIUM", "HIGH"):
        mids = [m for m, b in buckets.items() if b == bucket]
        if not mids:
            continue
        sub = obs[obs["manager_id"].isin(mids)]
        if len(sub) == 0:
            continue
        out[bucket] = score_fn(sub)
    return out
