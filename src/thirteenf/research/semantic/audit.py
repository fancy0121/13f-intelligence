"""Semantic audit computations (Q1-Q7 + diagnostics). Outcome-blind."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from thirteenf.research.resolution.coverage import (
    build_observation_frames,
    load_availability,
    load_master,
)
from thirteenf.research.semantic.classifier import classify_cusip
from thirteenf.research.semantic.taxonomy import (
    OPERATING_TYPES,
    POOLED_TYPES,
    ClassificationStatus,
    EconomicType,
)


VERIFIED_RESOLUTION = frozenset(
    {"VERIFIED_EXACT", "VERIFIED_MULTI_SOURCE", "VERIFIED_HISTORICAL"}
)


def majority_title(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT cusip, title_of_class
        FROM (
            SELECT cusip, title_of_class,
                   ROW_NUMBER() OVER (
                       PARTITION BY cusip
                       ORDER BY COUNT(*) DESC, title_of_class ASC
                   ) AS rn
            FROM holdings
            WHERE title_of_class != ''
            GROUP BY cusip, title_of_class
        )
        WHERE rn = 1
        """
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def openfigi_records(cache_dir: Path, cusip: str) -> list[dict]:
    p = cache_dir / "openfigi" / f"ID_CUSIP_{cusip}.json"
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        entry = d.get("entry") or {}
        return list(entry.get("data") or [])
    except (ValueError, OSError):
        return []


def classify_all(
    conn: sqlite3.Connection,
    cache_dir: Path,
) -> pd.DataFrame:
    """Classify the full eligible universe; returns the machine artifact."""
    securities = conn.execute(
        "SELECT cusip, issuer FROM securities WHERE cusip != ''"
    ).fetchall()
    titles = majority_title(conn)
    rows = []
    for cusip, issuer in securities:
        res = classify_cusip(
            cusip, issuer, titles.get(cusip), openfigi_records(cache_dir, cusip)
        )
        rows.append(
            {
                "cusip": cusip,
                "issuer": issuer or "",
                "title_of_class": titles.get(cusip, ""),
                "economic_type": res.economic_type,
                "classification_status": res.classification_status,
                "classification_sources": ";".join(res.classification_sources),
                "classification_reason": res.classification_reason,
                "classification_version": res.classification_version,
            }
        )
    return pd.DataFrame(rows)


def _merge_type(df: pd.DataFrame, class_df: pd.DataFrame) -> pd.DataFrame:
    m = class_df[["cusip", "economic_type", "classification_status"]].set_index("cusip")
    out = df.copy()
    out["economic_type"] = out["cusip"].map(m["economic_type"]).fillna(EconomicType.UNKNOWN.value)
    out["classification_status"] = out["cusip"].map(m["classification_status"]).fillna("UNKNOWN")
    return out


def composition_table(df: pd.DataFrame, value_col: str = "cusip") -> pd.DataFrame:
    g = df.groupby("economic_type")[value_col].nunique() if value_col == "cusip" else df.groupby("economic_type").size()
    if value_col != "cusip":
        g = df.groupby("economic_type").size()
    total = int(g.sum())
    out = g.rename("n").reset_index()
    out["pct"] = (out["n"] / total * 100).round(3) if total else 0.0
    return out


def compute_q1(class_df: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict:
    eligible = set(frames["O0"]["cusip"])
    sec_df = class_df[class_df["cusip"].isin(eligible)]
    sec = composition_table(sec_df)
    obs = composition_table(_merge_type(frames["O0"], class_df), value_col="obs")
    return {"security_level": sec.to_dict("records"),
            "observation_level": obs.to_dict("records"),
            "security_total": int(sec["n"].sum()),
            "observation_total": int(obs["n"].sum())}


def compute_q2(frames: dict[str, pd.DataFrame], class_df: pd.DataFrame) -> dict:
    out = {}
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        merged = _merge_type(frames[variant], class_df)
        t = composition_table(merged, value_col="obs")
        out[variant] = t.to_dict("records")
    return out


def compute_q3(frames: dict[str, pd.DataFrame], class_df: pd.DataFrame) -> dict:
    parts = ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined")
    merged = _merge_type(frames["O0"], class_df)
    rows = []
    overall = merged.groupby("economic_type").size()
    overall_share = (overall / overall.sum() * 100).to_dict()
    for p in parts:
        sub = merged[merged["part"] == p]
        if len(sub) == 0:
            continue
        g = sub.groupby("economic_type").size()
        share = (g / g.sum() * 100).to_dict()
        for etype in sorted(set(overall_share) | set(share)):
            rows.append({
                "split": p,
                "economic_type": etype,
                "n": int(g.get(etype, 0)),
                "share_pct": round(share.get(etype, 0.0), 3),
                "overall_share_pct": round(overall_share.get(etype, 0.0), 3),
                "delta_pp": round(share.get(etype, 0.0) - overall_share.get(etype, 0.0), 3),
            })
    flag = any(abs(r["delta_pp"]) > 5.0 for r in rows)
    return {"rows": rows, "SECURITY_TYPE_SPLIT_SHIFT": flag}


def compute_q4(master: pd.DataFrame, class_df: pd.DataFrame) -> dict:
    m = master.merge(class_df[["cusip", "economic_type"]], on="cusip", how="left")
    m["economic_type"] = m["economic_type"].fillna(EconomicType.UNKNOWN.value)
    out = {}
    for etype, sub in m.groupby("economic_type"):
        counts = sub["status"].value_counts().to_dict()
        verified = sum(v for k, v in counts.items() if k in VERIFIED_RESOLUTION)
        out[etype] = {
            "securities": int(len(sub)),
            "resolver_verified": verified,
            "resolution_rate_pct": round(verified / len(sub) * 100, 3) if len(sub) else None,
            "status_counts": counts,
        }
    return out


def failure_reason(status: str, notes: str, etype: str) -> str:
    if status == "NON_EQUITY_OR_UNSUPPORTED":
        return "NON_EQUITY"
    if status == "CONFLICT":
        if "ADR" in notes or "ADS" in notes:
            return "ADR_OR_ORDINARY_AMBIGUITY"
        if "shareClassFIGI" in notes or "share class" in notes:
            return "SHARE_CLASS_AMBIGUITY"
        return "NAME_OR_ENTITY_CONFLICT"
    if status == "AMBIGUOUS":
        if "multiple distinct US tickers" in notes:
            return "OPENFIGI_MULTI_MATCH"
        return "NAME_OR_ENTITY_CONFLICT"
    if status == "UNRESOLVED":
        if etype in POOLED_TYPES:
            return "FUND_OR_ETF_IDENTITY_PATH_MISSING"
        if "no US venue" in notes:
            return "DELISTED_OR_TERMINATED"
        if "no SEC issuer corroboration" in notes:
            return "SEC_CORROBORATION_MISSING"
        return "UNKNOWN_REASON"
    return "UNKNOWN_REASON"


def compute_q5(master: pd.DataFrame, class_df: pd.DataFrame) -> dict:
    m = master.merge(class_df[["cusip", "economic_type"]], on="cusip", how="left")
    m["economic_type"] = m["economic_type"].fillna(EconomicType.UNKNOWN.value)
    non_verified = m[~m["status"].isin(VERIFIED_RESOLUTION)].copy()
    non_verified["failure_reason"] = non_verified.apply(
        lambda r: failure_reason(r["status"], r.get("notes", ""), r["economic_type"]),
        axis=1,
    )
    g = non_verified.groupby("failure_reason").size().sort_values(ascending=False)
    total = int(g.sum())
    rows = []
    for reason, n in g.items():
        sub = non_verified[non_verified["failure_reason"] == reason]
        rows.append({
            "failure_reason": reason,
            "securities": int(n),
            "pct": round(n / total * 100, 3) if total else 0.0,
            "top_status": sub["status"].value_counts().head(1).to_dict(),
        })
    return {"total_non_verified": total, "rows": rows}


def compute_q6(
    frames: dict[str, pd.DataFrame],
    master: pd.DataFrame,
    availability: pd.DataFrame | None,
    class_df: pd.DataFrame,
) -> dict:
    op = set(class_df.loc[class_df["economic_type"].isin(OPERATING_TYPES), "cusip"])
    ver = set(master.loc[master["status"].isin(VERIFIED_RESOLUTION), "cusip"])
    sym_of = dict(zip(master["cusip"], master["symbol"]))
    avail_start = {}
    if availability is not None and len(availability):
        avail_start = dict(zip(availability["symbol"], availability["first_trade_date"]))
    def covered(cusip, info_date):
        if cusip not in op or cusip not in ver:
            return False
        sym = sym_of.get(cusip)
        start = avail_start.get(sym) if sym else None
        return bool(sym and start and str(start) <= str(info_date))
    out = {}
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        df = frames[variant]
        op_df = df[df["cusip"].isin(op)]
        elig = len(op_df)
        cov = sum(1 for _, r in op_df.iterrows() if covered(r["cusip"], r["info_date"]))
        out[variant] = {
            "eligible_observations": elig,
            "resolved_observations": cov,
            "coverage_pct": round(cov / elig * 100, 3) if elig else None,
        }
        for part in ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined"):
            sub = op_df[op_df["part"] == part]
            if len(sub) == 0:
                out[variant][part] = {"n": 0, "coverage": None}
                continue
            c = sum(1 for _, r in sub.iterrows() if covered(r["cusip"], r["info_date"]))
            out[variant][part] = {"n": len(sub), "resolved": c,
                                  "coverage": round(c / len(sub) * 100, 3)}
        pos = op_df[op_df["activity"] == "positive"]
        neg = op_df[op_df["activity"] == "negative"]
        out[variant]["positive"] = {
            "n": len(pos),
            "coverage": round(sum(1 for _, r in pos.iterrows() if covered(r["cusip"], r["info_date"])) / len(pos) * 100, 3) if len(pos) else None,
        }
        out[variant]["negative"] = {
            "n": len(neg),
            "coverage": round(sum(1 for _, r in neg.iterrows() if covered(r["cusip"], r["info_date"])) / len(neg) * 100, 3) if len(neg) else None,
        }
    op_sec = len(op & ver)
    out["security_level"] = {
        "operating_securities": len(op),
        "resolver_verified": op_sec,
        "rate_pct": round(op_sec / len(op) * 100, 3) if op else None,
    }
    return out


def _direction(ct: str) -> int:
    if ct in ("NEW", "ADD"):
        return 1
    if ct in ("REDUCE", "EXIT"):
        return -1
    return 0


def reversal_rate(obs: pd.DataFrame) -> float | None:
    work = obs[["manager_id", "security_id", "report_period", "change_type"]].copy()
    work["direction"] = work["change_type"].map(_direction)
    work = work[work["direction"] != 0].sort_values(["manager_id", "security_id", "report_period"])
    work["prev_dir"] = work.groupby(["manager_id", "security_id"])["direction"].shift(1)
    pairs = work.dropna(subset=["prev_dir"])
    if len(pairs) == 0:
        return None
    return float((pairs["direction"] != pairs["prev_dir"]).mean())


def compute_q7(
    frames: dict[str, pd.DataFrame],
    class_df: pd.DataFrame,
    conn: sqlite3.Connection,
) -> dict:
    obs = _merge_type(frames["O0"], class_df)
    o2 = _merge_type(frames["O1_2Q"], class_df)
    o3 = _merge_type(frames["O1_3Q"], class_df)
    groups = {
        "OPERATING": obs[obs["economic_type"].isin(OPERATING_TYPES)],
        "POOLED": obs[obs["economic_type"].isin(POOLED_TYPES)],
    }
    rows = {}
    for name, sub in groups.items():
        total = len(sub)
        if total == 0:
            rows[name] = {"n": 0}
            continue
        action = sub["change_type"].value_counts()
        act = {
            "NEW": float(action.get("NEW", 0) / total),
            "ADD": float(action.get("ADD", 0) / total),
            "REDUCE": float(action.get("REDUCE", 0) / total),
            "EXIT": float(action.get("EXIT", 0) / total),
            "UNCHANGED": float(action.get("UNCHANGED", 0) / total),
        }
        directional = action.get("NEW", 0) + action.get("ADD", 0) + action.get("REDUCE", 0) + action.get("EXIT", 0)
        turnover = (action.get("NEW", 0) + action.get("EXIT", 0)) / directional if directional else None
        p2 = o2[o2["cusip"].isin(set(sub["cusip"]))]
        p3 = o3[o3["cusip"].isin(set(sub["cusip"]))]
        # persistence eligibility rate: fraction of O0 obs also in O1_2Q/O1_3Q
        key = set(map(tuple, sub[["manager_id", "security_id", "report_period"]].itertuples(index=False)))
        key2 = set(map(tuple, p2[["manager_id", "security_id", "report_period"]].itertuples(index=False)))
        key3 = set(map(tuple, p3[["manager_id", "security_id", "report_period"]].itertuples(index=False)))
        elig2 = sum(1 for k in key if k in key2) / total if total else None
        elig3 = sum(1 for k in key if k in key3) / total if total else None
        weights = sub["weight_now"].dropna()
        pos_counts = sub.groupby(["manager_id", "report_period"]).size()
        mgr_per_sec = sub.groupby("cusip")["manager_id"].nunique()
        rows[name] = {
            "n_observations": total,
            "action_rates": act,
            "turnover_proxy": round(turnover, 6) if turnover is not None else None,
            "persistence_2q_rate": round(elig2, 6) if elig2 is not None else None,
            "persistence_3q_rate": round(elig3, 6) if elig3 is not None else None,
            "weight_mean": round(float(weights.mean()), 6) if len(weights) else None,
            "weight_median": round(float(weights.median()), 6) if len(weights) else None,
            "weight_p25": round(float(weights.quantile(0.25)), 6) if len(weights) else None,
            "weight_p75": round(float(weights.quantile(0.75)), 6) if len(weights) else None,
            "positions_per_filing_mean": round(float(pos_counts.mean()), 3) if len(pos_counts) else None,
            "positions_per_filing_median": round(float(pos_counts.median()), 3) if len(pos_counts) else None,
            "managers_per_security_mean": round(float(mgr_per_sec.mean()), 3) if len(mgr_per_sec) else None,
            "managers_per_security_median": round(float(mgr_per_sec.median()), 3) if len(mgr_per_sec) else None,
            "reversal_rate": round(reversal_rate(sub), 6) if reversal_rate(sub) is not None else None,
        }
    # manager control: within-manager operating vs pooled NEW+ADD rate
    man_rows = []
    for mid, g in obs.groupby("manager_id"):
        op = g[g["economic_type"].isin(OPERATING_TYPES)]
        po = g[g["economic_type"].isin(POOLED_TYPES)]
        if len(op) == 0 or len(po) == 0:
            continue
        def posrate(x):
            return float((x["change_type"].isin(("NEW", "ADD"))).mean())
        man_rows.append({
            "manager_id": int(mid),
            "operating_positive_rate": round(posrate(op), 6),
            "pooled_positive_rate": round(posrate(po), 6),
            "diff_pp": round((posrate(op) - posrate(po)) * 100, 3),
            "n_operating": int(len(op)),
            "n_pooled": int(len(po)),
        })
    man_df = pd.DataFrame(man_rows)
    manager_confound = None
    if len(man_df):
        abs_gap = man_df["diff_pp"].abs().sum()
        top3 = man_df["diff_pp"].abs().sort_values(ascending=False).head(3).sum()
        manager_confound = (top3 / abs_gap) > 0.5 if abs_gap else False
    # time control: per quarter operating vs pooled positive rate
    qrows = []
    for q, g in obs.groupby("report_period"):
        op = g[g["economic_type"].isin(OPERATING_TYPES)]
        po = g[g["economic_type"].isin(POOLED_TYPES)]
        if len(op) == 0 or len(po) == 0:
            continue
        def posrate(x):
            return float((x["change_type"].isin(("NEW", "ADD"))).mean())
        qrows.append({"quarter": q, "operating_positive_rate": round(posrate(op), 6),
                      "pooled_positive_rate": round(posrate(po), 6),
                      "diff_pp": round((posrate(op) - posrate(po)) * 100, 3),
                      "n": int(len(g))})
    qdf = pd.DataFrame(qrows)
    time_sensitive = None
    if len(qdf):
        vals = qdf["diff_pp"].dropna()
        time_sensitive = bool((vals.max() - vals.min()) > 10.0) if len(vals) else None
    return {
        "groups": rows,
        "manager_control": man_df.to_dict("records") if len(man_df) else [],
        "manager_composition_confounded": manager_confound,
        "time_control": qdf.to_dict("records") if len(qdf) else [],
        "time_composition_sensitive": time_sensitive,
    }


def compute_selection_bias(
    frames: dict[str, pd.DataFrame],
    class_df: pd.DataFrame,
) -> dict:
    obs = _merge_type(frames["O0"], class_df)
    op = obs[obs["economic_type"].isin(OPERATING_TYPES)]
    out = {}
    for dim, col in (
        ("manager", "manager_id"),
        ("quarter", "report_period"),
        ("direction", "activity"),
        ("split", "part"),
    ):
        broad = obs[col].value_counts(normalize=True) * 100
        sel = op[col].value_counts(normalize=True) * 100
        rows = []
        for k in sorted(set(broad.index) | set(sel.index)):
            rows.append({
                dim + "_key": k,
                "broad_share_pct": round(float(broad.get(k, 0.0)), 3),
                "operating_share_pct": round(float(sel.get(k, 0.0)), 3),
                "delta_pp": round(float(sel.get(k, 0.0) - broad.get(k, 0.0)), 3),
            })
        out[dim] = rows
    # position size and persistence
    broad_w = obs["weight_now"].dropna()
    op_w = op["weight_now"].dropna()
    out["position_size"] = {
        "broad_mean": round(float(broad_w.mean()), 6) if len(broad_w) else None,
        "operating_mean": round(float(op_w.mean()), 6) if len(op_w) else None,
        "broad_median": round(float(broad_w.median()), 6) if len(broad_w) else None,
        "operating_median": round(float(op_w.median()), 6) if len(op_w) else None,
    }
    out["frequency"] = {
        "broad_mean_obs_per_security": round(float(obs.groupby("cusip").size().mean()), 3),
        "operating_mean_obs_per_security": round(float(op.groupby("cusip").size().mean()), 3),
    }
    return out


def compute_missingness(
    frames: dict[str, pd.DataFrame],
    master: pd.DataFrame,
    availability: pd.DataFrame | None,
    class_df: pd.DataFrame,
) -> dict:
    op = set(class_df.loc[class_df["economic_type"].isin(OPERATING_TYPES), "cusip"])
    ver = set(master.loc[master["status"].isin(VERIFIED_RESOLUTION), "cusip"])
    sym_of = dict(zip(master["cusip"], master["symbol"]))
    avail_start = {}
    if availability is not None and len(availability):
        avail_start = dict(zip(availability["symbol"], availability["first_trade_date"]))
    obs = _merge_type(frames["O0"], class_df)
    op_df = obs[obs["cusip"].isin(op)].copy()
    def covered(cusip, info_date):
        if cusip not in ver:
            return False
        sym = sym_of.get(cusip)
        start = avail_start.get(sym) if sym else None
        return bool(sym and start and str(start) <= str(info_date))
    op_df["mapped"] = op_df.apply(lambda r: covered(r["cusip"], r["info_date"]), axis=1)
    out = {}
    for dim, col in (
        ("manager", "manager_id"),
        ("quarter", "report_period"),
        ("direction", "activity"),
        ("split", "part"),
    ):
        g = pd.crosstab(op_df[col], op_df["mapped"])
        rows = []
        for k in g.index:
            mapped = int(g.loc[k, True]) if True in g.columns else 0
            unmapped = int(g.loc[k, False]) if False in g.columns else 0
            total = mapped + unmapped
            rows.append({
                dim + "_key": k, "mapped": mapped, "unmapped": unmapped,
                "missing_pct": round(unmapped / total * 100, 3) if total else None,
            })
        out[dim] = rows
    unmapped = int((~op_df["mapped"]).sum())
    total = len(op_df)
    miss_pct = unmapped / total * 100 if total else 0
    if miss_pct <= 10:
        status = "LOW_CONCERN"
    elif miss_pct <= 25:
        status = "MODERATE_CONCERN"
    elif miss_pct <= 50:
        status = "HIGH_CONCERN"
    else:
        status = "HIGH_CONCERN"
    out["overall"] = {
        "operating_observations": total,
        "unmapped_observations": unmapped,
        "missing_pct": round(miss_pct, 3),
        "OPERATING_EQUITY_MISSINGNESS_STATUS": status,
    }
    return out


def decompose_variant_bias(
    frames: dict[str, pd.DataFrame],
    master: pd.DataFrame,
    availability: pd.DataFrame | None,
    class_df: pd.DataFrame,
) -> dict:
    ver = set(master.loc[master["status"].isin(VERIFIED_RESOLUTION), "cusip"])
    sym_of = dict(zip(master["cusip"], master["symbol"]))
    avail_start = {}
    if availability is not None and len(availability):
        avail_start = dict(zip(availability["symbol"], availability["first_trade_date"]))
    def covered(cusip, info_date):
        if cusip not in ver:
            return False
        sym = sym_of.get(cusip)
        start = avail_start.get(sym) if sym else None
        return bool(sym and start and str(start) <= str(info_date))
    out = {}
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        df = _merge_type(frames[variant], class_df)
        overall = sum(1 for _, r in df.iterrows() if covered(r["cusip"], r["info_date"])) / len(df) * 100
        within = {}
        for etype, sub in df.groupby("economic_type"):
            if len(sub) == 0:
                continue
            c = sum(1 for _, r in sub.iterrows() if covered(r["cusip"], r["info_date"]))
            within[etype] = round(c / len(sub) * 100, 3)
        out[variant] = {"overall": round(overall, 3), "within_type": within}
    return out


def load_classification(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")
