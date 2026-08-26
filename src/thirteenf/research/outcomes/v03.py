"""v0.3 Operating Equity Outcome Validation (frozen protocol).

Universe: v0.2.2 semantic manifest, OPERATING types with VERIFIED
classification. Resolver frozen. Missingness gates M1-M5. Outcome-blind until
the protocol freeze (ad4139a).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from thirteenf.research.outcomes.execution import (
    attach_returns,
    concentration_audit,
    evaluate_grid,
    fetch_yahoo_series,
    run_null,
)
from thirteenf.research.resolution.coverage import (
    build_observation_frames,
    load_availability,
    load_master,
)
from thirteenf.research.semantic.taxonomy import OPERATING_TYPES


VERIFIED_RESOLUTION = frozenset(
    {"VERIFIED_EXACT", "VERIFIED_MULTI_SOURCE", "VERIFIED_HISTORICAL"}
)
PARTS = ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined")


def load_v03_universe(class_path: str) -> pd.DataFrame:
    """Primary universe: OPERATING types AND classification_status=VERIFIED."""
    c = pd.read_csv(class_path, dtype=str).fillna("")
    return c[
        c["economic_type"].isin(OPERATING_TYPES)
        & (c["classification_status"] == "VERIFIED")
    ].copy()


def filter_frames(frames: dict[str, pd.DataFrame], universe: set[str]) -> dict[str, pd.DataFrame]:
    return {v: df[df["cusip"].isin(universe)].copy() for v, df in frames.items()}


def _covered(cusip, info_date, ver, sym_of, avail_start) -> bool:
    if cusip not in ver:
        return False
    sym = sym_of.get(cusip)
    start = avail_start.get(sym) if sym else None
    return bool(sym and start and str(start) <= str(info_date))


def _resolve_maps(master: pd.DataFrame, availability: pd.DataFrame | None):
    ver = set(master.loc[master["status"].isin(VERIFIED_RESOLUTION), "cusip"])
    sym_of = dict(zip(master["cusip"], master["symbol"]))
    avail_start = {}
    if availability is not None and len(availability):
        avail_start = dict(zip(availability["symbol"], availability["first_trade_date"]))
    return ver, sym_of, avail_start


def compute_missingness_gates(
    frames: dict[str, pd.DataFrame],
    universe: set[str],
    master: pd.DataFrame,
    availability: pd.DataFrame | None,
) -> dict:
    ver, sym_of, avail_start = _resolve_maps(master, availability)

    def cov(df: pd.DataFrame) -> float:
        if len(df) == 0:
            return 0.0
        return sum(1 for _, r in df.iterrows() if _covered(r["cusip"], r["info_date"], ver, sym_of, avail_start)) / len(df) * 100

    out = {}
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        df = frames[variant]
        overall = cov(df)
        per_split = {p: cov(df[df["part"] == p]) for p in PARTS}
        pos = cov(df[df["activity"] == "positive"])
        neg = cov(df[df["activity"] == "negative"])
        out[variant] = {
            "eligible": int(len(df)),
            "overall_coverage": round(overall, 3),
            "per_split": {p: round(v, 3) for p, v in per_split.items()},
            "positive_coverage": round(pos, 3),
            "negative_coverage": round(neg, 3),
        }
    o0 = out["O0"]
    # M1
    m1 = o0["overall_coverage"] >= 80.0
    # M2 (each split >=75 on O0)
    m2 = all(v >= 75.0 for v in o0["per_split"].values())
    # M3 dev vs holdouts
    dev = o0["per_split"]["H0_dev"]
    m3 = all(abs(dev - v) <= 7.5 for p, v in o0["per_split"].items() if p != "H0_dev")
    # M4 directional
    m4 = abs(o0["positive_coverage"] - o0["negative_coverage"]) <= 7.5
    # M5 variant
    gaps = [abs(out[v]["overall_coverage"] - o0["overall_coverage"]) for v in ("O1_2Q", "O1_3Q")]
    m5 = all(g <= 7.5 for g in gaps)
    gates = {
        "M1_overall_80": {"value": o0["overall_coverage"], "PASS": m1},
        "M2_split_75": {"value": o0["per_split"], "PASS": m2},
        "M3_differential_7.5": {"value": {p: round(abs(dev - v), 3) for p, v in o0["per_split"].items() if p != "H0_dev"}, "PASS": m3},
        "M4_directional_7.5": {"value": round(abs(o0["positive_coverage"] - o0["negative_coverage"]), 3), "PASS": m4},
        "M5_variant_7.5": {"value": {v: round(g, 3) for v, g in zip(("O1_2Q", "O1_3Q"), gaps)}, "PASS": m5},
    }
    all_pass = m1 and m2 and m3 and m4 and m5
    return {
        "variants": out,
        "gates": gates,
        "MISSINGNESS_GOVERNANCE_STATUS": "PASS" if all_pass else "FAIL",
    }


def load_price_map(cache_dir: Path, symbols: list[str]) -> dict[str, dict]:
    price_map = {}
    for sym in symbols:
        p = cache_dir / "yahoo_full" / f"{sym.replace('^', '_')}.json"
        if p.exists():
            price_map[sym] = json.loads(p.read_text(encoding="utf-8"))
    return price_map


def run_v03(
    conn,
    class_path: str,
    master_path: str,
    avail_path: str,
    cache_dir: Path,
    out_dir: Path,
) -> dict:
    universe_df = load_v03_universe(class_path)
    universe = set(universe_df["cusip"])
    frames_all = build_observation_frames(conn)
    frames = filter_frames(frames_all, universe)
    master = load_master(master_path)
    availability = load_availability(avail_path) if Path(avail_path).exists() else None

    miss = compute_missingness_gates(frames, universe, master, availability)

    # mapping coverage by type
    ver, sym_of, avail_start = _resolve_maps(master, availability)
    cov_by_type = {}
    for etype, sub in universe_df.groupby("economic_type"):
        sub_cusips = set(sub["cusip"])
        df = frames["O0"]
        obs = df[df["cusip"].isin(sub_cusips)]
        c = sum(1 for _, r in obs.iterrows() if _covered(r["cusip"], r["info_date"], ver, sym_of, avail_start))
        cov_by_type[etype] = {
            "securities": int(len(sub)),
            "observations": int(len(obs)),
            "resolved_observations": int(c),
            "observation_coverage": round(c / len(obs) * 100, 3) if len(obs) else None,
        }

    # outcome execution
    symbol_of = {
        r["cusip"]: r["symbol"]
        for r in master.to_dict("records")
        if r["status"] in VERIFIED_RESOLUTION and r["symbol"]
    }
    symbols = sorted({s for s in symbol_of.values() if s})
    price_map = load_price_map(cache_dir, symbols)
    bench = price_map.get("^GSPC")
    if bench is None:
        bench = fetch_yahoo_series("^GSPC", cache_dir)
        price_map["^GSPC"] = bench
    datasets = attach_returns(frames, symbol_of, price_map, bench)
    grid = evaluate_grid(datasets)
    nulls = {v: {h: run_null(datasets, v, h) for h in ("3M", "6M", "12M")} for v in ("O0", "O1_2Q", "O1_3Q")}
    conc = {v: {h: concentration_audit(datasets, v, h) for h in ("3M", "6M", "12M")} for v in ("O0", "O1_2Q", "O1_3Q")}

    # missingness sensitivity (resolved vs unresolved composition within universe)
    sens = missingness_sensitivity(frames["O0"], universe, ver, sym_of, avail_start)

    # time regime (per quarter excess median on dev)
    time_regime = {}
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        dev = datasets[variant][datasets[variant]["part"] == "H0_dev"]
        time_regime[variant] = {
            q: round(float(g["excess_3M"].median()), 6)
            for q, g in dev.dropna(subset=["excess_3M"]).groupby("report_period")
            if len(g) >= 30
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    results = {
        "universe_securities": len(universe),
        "universe_by_type": universe_df["economic_type"].value_counts().to_dict(),
        "missingness": miss,
        "mapping_coverage_by_type": cov_by_type,
        "outcome_grid": grid,
        "null": nulls,
        "concentration": conc,
        "missingness_sensitivity": sens,
        "time_regime_median_excess_3M": time_regime,
        "right_censored": {v: {h: int(datasets[v][f"censored_{h}"].sum()) for h in ("3M", "6M", "12M")} for v in ("O0", "O1_2Q", "O1_3Q")},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "v0_3_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return results


def missingness_sensitivity(df, universe, ver, sym_of, avail_start) -> dict:
    work = df.copy()
    work["mapped"] = work.apply(
        lambda r: _covered(r["cusip"], r["info_date"], ver, sym_of, avail_start), axis=1
    )
    out = {}
    for dim, col in (
        ("manager", "manager_id"),
        ("quarter", "report_period"),
        ("direction", "activity"),
        ("split", "part"),
    ):
        g = pd.crosstab(work[col], work["mapped"])
        rows = []
        for k in g.index:
            mapped = int(g.loc[k, True]) if True in g.columns else 0
            unmapped = int(g.loc[k, False]) if False in g.columns else 0
            total = mapped + unmapped
            rows.append({dim + "_key": k, "mapped": mapped, "unmapped": unmapped,
                         "missing_pct": round(unmapped / total * 100, 3) if total else None})
        out[dim] = rows
    return out


def falsify(
    grid: dict,
    nulls: dict,
    conc: dict,
    miss: dict,
) -> dict:
    """Mechanical pre-registered falsification / simplicity / stop / candidate."""
    H = "3M"

    def med(variant, part):
        return grid.get(variant, {}).get(part, {}).get(H, {}).get("median")

    def downside(variant, part):
        return grid.get(variant, {}).get(part, {}).get(H, {}).get("downside_rate")

    o0_dev = med("O0", "H0_dev")
    o1_dev = med("O1_2Q", "H0_dev")
    o2_dev = med("O1_3Q", "H0_dev")
    o0_h1 = med("O0", "H1_time_holdout")
    o1_h1 = med("O1_2Q", "H1_time_holdout")
    o2_h1 = med("O1_3Q", "H1_time_holdout")
    o0_h4 = med("O0", "H4_combined")
    o1_h4 = med("O1_2Q", "H4_combined")

    fail_o1 = []
    if o0_h1 is not None and o1_h1 is not None and (o0_h1 > 0) != (o1_h1 > 0):
        fail_o1.append("TIME_HOLDOUT_DIRECTION_REVERSES")
    if o0_h4 is not None and o1_h4 is not None and (o0_h4 > 0) != (o1_h4 > 0):
        fail_o1.append("COMBINED_HOLDOUT_DIRECTION_REVERSES")
    if o0_dev is not None and o1_dev is not None and abs(o1_dev - o0_dev) < 0.01:
        fail_o1.append("NO_MEANINGFUL_IMPROVEMENT_OVER_O0")
    n1 = nulls.get("O1_2Q", {}).get(H, {})
    if n1.get("exceeds_null_p95") is not True:
        fail_o1.append("NULL_COMPARISON_FAILS")
    c1 = conc.get("O1_2Q", {}).get(H, {})
    if "leave_one_manager_out" in c1:
        base = c1.get("base_median")
        lomo = c1["leave_one_manager_out"]
        if base is not None:
            flips = sum(1 for v in lomo.values() if v is not None and (v > 0) != (base > 0))
            if lomo and flips / len(lomo) > 0.3:
                fail_o1.append("MANAGER_DOMINATED")
    if "top_securities" in c1 and c1.get("top_securities"):
        n_obs = c1.get("n_obs") or 0
        top_share = c1["top_securities"][0]["count"] / n_obs if n_obs else 0.0
        if top_share > 0.1:
            fail_o1.append("SECURITY_DOMINATED")
    if miss.get("MISSINGNESS_GOVERNANCE_STATUS") != "PASS":
        fail_o1.append("MISSINGNESS_GATES_FAIL")
    d0 = downside("O0", "H0_dev")
    d1 = downside("O1_2Q", "H0_dev")
    if d0 is not None and d1 is not None and d1 >= d0 and (o1_dev is None or o0_dev is None or abs(o1_dev - o0_dev) < 0.01):
        fail_o1.append("DOWNSIDE_NOT_IMPROVED_AND_GAIN_TRIVIAL")

    fail_o2 = list(fail_o1)
    if o1_dev is not None and o2_dev is not None and abs(o2_dev - o1_dev) < 0.01:
        fail_o2.append("NO_INCREMENT_OVER_O1")
    if o2_dev is None:
        fail_o2.append("INSUFFICIENT_SAMPLE")

    o1_pass = len(fail_o1) == 0
    o2_pass = len(fail_o2) == 0
    if o1_pass and not o2_pass:
        simplest = "O1"
    elif o1_pass and o2_pass:
        simplest = "O2"
    elif not o1_pass and not o2_pass:
        simplest = "O0"
    else:
        simplest = "O0"
    stop_triggered = (not o1_pass) and (not o2_pass)
    candidate = "READY_FOR_EXTERNAL_REVIEW" if (o1_pass or o2_pass) and miss.get("MISSINGNESS_GOVERNANCE_STATUS") == "PASS" else "NO_CANDIDATE"
    return {
        "O1_FAIL_REASONS": fail_o1,
        "O2_FAIL_REASONS": fail_o2,
        "O1_PASS": o1_pass,
        "O2_PASS": o2_pass,
        "SIMPLEST_SURVIVING_MODEL": simplest,
        "PREDICTIVE_RESEARCH_STOP_RULE": "TRIGGERED" if stop_triggered else "NOT_TRIGGERED",
        "PRODUCT_CANDIDATE_STATUS": candidate,
        "notes": {
            "o0_dev_median_3M": o0_dev,
            "o1_dev_median_3M": o1_dev,
            "o2_dev_median_3M": o2_dev,
            "o1_null_p95_3M": n1.get("null_p95"),
            "o1_exceeds_null_p95": n1.get("exceeds_null_p95"),
        },
    }


def _md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def write_reports(results: dict, out_dir: Path, verdict: dict) -> None:
    miss = results["missingness"]
    lines = ["# v0.3 Missingness Audit", "",
             f"MISSINGNESS_GOVERNANCE_STATUS={miss['MISSINGNESS_GOVERNANCE_STATUS']}", "",
             "## Gates M1-M5", "",
             _md_table(["gate", "value", "PASS"],
                       [{"gate": k, "value": json.dumps(v["value"], ensure_ascii=False), "PASS": v["PASS"]}
                        for k, v in miss["gates"].items()]),
             "",
             "## Per variant", "",
             _md_table(["variant", "eligible", "overall_coverage", "positive", "negative"],
                       [{"variant": k, "eligible": v["eligible"], "overall_coverage": v["overall_coverage"],
                         "positive": v["positive_coverage"], "negative": v["negative_coverage"]}
                        for k, v in miss["variants"].items()]),
             "",
             "## Per split (O0)", "",
             _md_table(["split", "coverage"], [{"split": k, "coverage": v} for k, v in miss["variants"]["O0"]["per_split"].items()]),
             ""]
    (out_dir / "v0_3_missingness_audit.md").write_text("\n".join(lines), encoding="utf-8")

    cov = results["mapping_coverage_by_type"]
    lines = ["# v0.3 Mapping Coverage", "",
             f"Universe securities: {results['universe_securities']}", "",
             _md_table(["economic_type", "securities", "observations", "resolved_observations", "observation_coverage"],
                       [{"economic_type": k, **v} for k, v in cov.items()]),
             ""]
    (out_dir / "v0_3_mapping_coverage.md").write_text("\n".join(lines), encoding="utf-8")

    grid = results["outcome_grid"]
    lines = ["# v0.3 Outcome Results", "",
             "Excess return vs ^GSPC; horizons 3M=63/6M=126/12M=252 trading days.", "",
             "## O0", "",
             _md_table(["split", "horizon", "n_ret", "mean", "median", "hit_rate", "std", "negative_rate", "mean_negative"],
                       [{"split": p, "horizon": h, **grid["O0"][p][h]}
                        for p in ("ALL",) + PARTS for h in ("3M", "6M", "12M")
                        if isinstance(grid["O0"].get(p), dict) and isinstance(grid["O0"][p].get(h), dict)]),
             "",
             "## O1_2Q", "",
             _md_table(["split", "horizon", "n_ret", "mean", "median", "hit_rate", "std", "negative_rate", "mean_negative"],
                       [{"split": p, "horizon": h, **grid["O1_2Q"][p][h]}
                        for p in ("ALL",) + PARTS for h in ("3M", "6M", "12M")
                        if isinstance(grid["O1_2Q"].get(p), dict) and isinstance(grid["O1_2Q"][p].get(h), dict)]),
             "",
             "## O1_3Q", "",
             _md_table(["split", "horizon", "n_ret", "mean", "median", "hit_rate", "std", "negative_rate", "mean_negative"],
                       [{"split": p, "horizon": h, **grid["O1_3Q"][p][h]}
                        for p in ("ALL",) + PARTS for h in ("3M", "6M", "12M")
                        if isinstance(grid["O1_3Q"].get(p), dict) and isinstance(grid["O1_3Q"][p].get(h), dict)]),
             ""]
    (out_dir / "v0_3_outcome_results.md").write_text("\n".join(lines), encoding="utf-8")

    lines = ["# v0.3 Holdout Results", "",
             "Per-variant holdout excess medians (3M/6M/12M).", "",
             _md_table(["variant", "split", "horizon", "median"],
                       [{"variant": v, "split": p, "horizon": h,
                         "median": grid[v].get(p, {}).get(h, {}).get("median")}
                        for v in ("O0", "O1_2Q", "O1_3Q") for p in PARTS for h in ("3M", "6M", "12M")]),
             ""]
    (out_dir / "v0_3_holdout_results.md").write_text("\n".join(lines), encoding="utf-8")

    nulls = results["null"]
    lines = ["# v0.3 Null Results", "",
             "Frozen null (NULL_SEED, 200 reps, dev cell).", "",
             _md_table(["variant", "horizon", "observed_median", "null_p95", "exceeds_null_p95", "n_obs"],
                       [{"variant": v, "horizon": h, **nulls[v][h]}
                        for v in ("O0", "O1_2Q", "O1_3Q") for h in ("3M", "6M", "12M")]),
             ""]
    (out_dir / "v0_3_null_results.md").write_text("\n".join(lines), encoding="utf-8")

    conc = results["concentration"]
    lines = ["# v0.3 Concentration Audit", "",
             "Leave-one-manager-out + top securities + time regime (dev, 3M).", "",
             _md_table(["variant", "horizon", "base_median", "n_managers", "top_security_share"],
                       [{"variant": v, "horizon": h,
                         "base_median": conc[v][h].get("base_median"),
                         "n_managers": len(conc[v][h].get("leave_one_manager_out", {})),
                         "top_security_share": round(conc[v][h]["top_securities"][0]["count"] / conc[v][h].get("n_obs", 1), 4) if conc[v][h].get("top_securities") else None}
                        for v in ("O0", "O1_2Q", "O1_3Q") for h in ("3M", "6M", "12M")]),
             ""]
    (out_dir / "v0_3_concentration_audit.md").write_text("\n".join(lines), encoding="utf-8")

    tr = results["time_regime_median_excess_3M"]
    lines = ["# v0.3 Time Regime Audit", "",
             "Per-quarter dev median excess (3M) by variant (>=30 obs).", "",
             _md_table(["quarter"] + list(tr.keys()),
                       [{"quarter": q, **{v: tr[v].get(q) for v in tr}} for q in sorted(set().union(*(set(v) for v in tr.values())))]),
             ""]
    (out_dir / "v0_3_time_regime_audit.md").write_text("\n".join(lines), encoding="utf-8")

    rc = results["right_censored"]
    lines = ["# v0.3 Falsification Report", "",
             "Mechanical application of pre-registered O1/O2 falsification criteria (3M primary).", "",
             _md_table(["item", "value"], [{"item": k, "value": json.dumps(v, ensure_ascii=False)} for k, v in verdict.items()]),
             "",
             "Right-censored counts:", "",
             _md_table(["variant", "horizon", "censored"],
                       [{"variant": v, "horizon": h, "censored": c} for v, hs in rc.items() for h, c in hs.items()]),
             ""]
    (out_dir / "v0_3_falsification_report.md").write_text("\n".join(lines), encoding="utf-8")

    lines = ["# v0.3 Final Recommendation", "",
             f"SIMPLEST_SURVIVING_MODEL={verdict['SIMPLEST_SURVIVING_MODEL']}", "",
             f"PREDICTIVE_RESEARCH_STOP_RULE={verdict['PREDICTIVE_RESEARCH_STOP_RULE']}", "",
             f"PRODUCT_CANDIDATE_STATUS={verdict['PRODUCT_CANDIDATE_STATUS']}", "",
             f"O1_PASS={verdict['O1_PASS']} O2_PASS={verdict['O2_PASS']}", "",
             "O1 fail reasons:", "", "\n".join(f"- {r}" for r in verdict["O1_FAIL_REASONS"]) or "- none", "",
             "O2 fail reasons:", "", "\n".join(f"- {r}" for r in verdict["O2_FAIL_REASONS"]) or "- none", "",
             ""]
    (out_dir / "v0_3_final_recommendation.md").write_text("\n".join(lines), encoding="utf-8")
