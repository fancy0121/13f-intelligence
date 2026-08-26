"""v0.3 Operating Equity outcome validation tests (synthetic, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.research.outcomes.execution import attach_returns
from thirteenf.research.outcomes.v03 import (
    compute_missingness_gates,
    falsify,
    filter_frames,
    load_v03_universe,
)


def _class_df(tmp_path):
    p = tmp_path / "classification.csv"
    p.write_text(
        "cusip,economic_type,classification_status,issuer,title_of_class,classification_sources,classification_reason,classification_version\n"
        "A,OPERATING_COMMON_EQUITY,VERIFIED,X,COM,openfigi,T8,v0.2.2\n"
        "B,OPERATING_ADR,VERIFIED,Y,SPONSORED ADS,openfigi,T5,v0.2.2\n"
        "C,OPERATING_COMMON_EQUITY,PROVISIONAL,Z,COM,sec_title,F5,v0.2.2\n"
        "D,ETF,VERIFIED,Q,ISHARES ETF,openfigi,T2,v0.2.2\n"
        "E,UNKNOWN,UNKNOWN,W,,,F7,v0.2.2\n",
        encoding="utf-8",
    )
    return str(p)


def test_universe_exact_reuse_no_leakage(tmp_path):
    u = load_v03_universe(_class_df(tmp_path))
    assert set(u["cusip"]) == {"A", "B"}
    assert not set(u["cusip"]) & {"C", "D", "E"}
    assert set(u["economic_type"]) == {"OPERATING_COMMON_EQUITY", "OPERATING_ADR"}


def test_filter_frames_excludes_pooled_unknown(tmp_path):
    u = set(load_v03_universe(_class_df(tmp_path))["cusip"])
    frames = {
        v: pd.DataFrame(
            {"cusip": ["A", "B", "C", "D", "E"],
             "info_date": ["2024-01-01"] * 5,
             "part": ["H0_dev"] * 5,
             "activity": ["positive"] * 5,
             "change_type": ["ADD"] * 5}
        )
        for v in ("O0", "O1_2Q", "O1_3Q")
    }
    f = filter_frames(frames, u)
    assert set(f["O0"]["cusip"]) == {"A", "B"}


def test_missingness_gates_m1_m5():
    parts = ["H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined"]
    rows = []
    for i, p in enumerate(parts):
        rows += [
            {"cusip": c, "info_date": "2024-01-01", "part": p,
             "activity": a, "change_type": ct}
            for c, a, ct in (("A", "positive", "ADD"), ("B", "negative", "REDUCE"), ("C", "positive", "ADD"))
        ]
    frames = {
        v: pd.DataFrame(
            rows
        )
        for v in ("O0", "O1_2Q", "O1_3Q")
    }
    master = pd.DataFrame(
        [
            {"cusip": "A", "status": "VERIFIED_EXACT", "symbol": "AAA"},
            {"cusip": "B", "status": "VERIFIED_EXACT", "symbol": "BBB"},
            {"cusip": "C", "status": "UNRESOLVED", "symbol": ""},
        ]
    )
    avail = pd.DataFrame(
        [
            {"symbol": "AAA", "first_trade_date": "2020-01-01"},
            {"symbol": "BBB", "first_trade_date": "2020-01-01"},
        ]
    )
    miss = compute_missingness_gates(frames, {"A", "B", "C"}, master, avail)
    assert miss["variants"]["O0"]["overall_coverage"] == 66.667
    assert miss["gates"]["M1_overall_80"]["PASS"] is False
    # all covered -> PASS
    miss2 = compute_missingness_gates(filter_frames(frames, {"A", "B"}), {"A", "B"}, master, avail)
    assert miss2["gates"]["M1_overall_80"]["PASS"] is True
    assert miss2["MISSINGNESS_GOVERNANCE_STATUS"] == "PASS"


def test_right_censoring_marked():
    frames = {"O0": pd.DataFrame(
        {"cusip": ["A"] * 5, "info_date": ["2024-01-01"] * 5,
         "part": ["H0_dev"] * 5, "activity": ["positive"] * 5,
         "change_type": ["ADD"] * 5})}
    import datetime
    dates = []
    d = datetime.date.fromisoformat("2024-01-01")
    while len(dates) < 100:
        if d.weekday() < 5:
            dates.append(d.isoformat())
        d += datetime.timedelta(days=1)
    price_map = {"AAA": {"dates": dates, "adjclose": list(range(100)), "splits": {}, "error": None}}
    datasets = attach_returns(frames, {"A": "AAA"}, price_map, {})
    assert int(datasets["O0"]["censored_12M"].sum()) == 5
    assert int(datasets["O0"]["censored_3M"].sum()) == 0


def test_holdout_preserved():
    frames = {"O0": pd.DataFrame(
        {"cusip": ["A", "A"], "info_date": ["2024-01-01"] * 2,
         "part": ["H0_dev", "H1_time_holdout"],
         "activity": ["positive", "negative"], "change_type": ["ADD", "REDUCE"]})}
    f = filter_frames(frames, {"A"})
    assert set(f["O0"]["part"]) == {"H0_dev", "H1_time_holdout"}


def _grid(variant, dev_med, h1_med, h4_med):
    def cell(m):
        return {"H0_dev": {"3M": {"median": dev_med, "downside_rate": 0.4}},
                "H1_time_holdout": {"3M": {"median": h1_med}},
                "H4_combined": {"3M": {"median": h4_med}}}
    return cell(dev_med)


def test_falsify_stop_rule_and_simplicity():
    # O1 and O2 both fail -> stop triggered, simplest O0, no candidate
    grid = {
        "O0": _grid("O0", 0.02, 0.02, 0.02),
        "O1_2Q": _grid("O1", 0.021, 0.021, 0.021),
        "O1_3Q": _grid("O2", 0.021, 0.021, 0.021),
    }
    # O1 no meaningful improvement (<1%) -> NO_MEANINGFUL_IMPROVEMENT_OVER_O0; null fails
    nulls = {
        "O1_2Q": {"3M": {"exceeds_null_p95": False, "null_p95": 0.03}},
        "O1_3Q": {"3M": {"exceeds_null_p95": False, "null_p95": 0.03}},
    }
    conc = {
        "O1_2Q": {"3M": {"base_median": 0.021, "leave_one_manager_out": {1: 0.02, 2: 0.02, 3: 0.02},
                          "top_securities": [{"count": 1}], "n_obs": 10}},
        "O1_3Q": {"3M": {"base_median": 0.021, "leave_one_manager_out": {1: 0.02},
                          "top_securities": [{"count": 1}], "n_obs": 10}},
    }
    miss = {"MISSINGNESS_GOVERNANCE_STATUS": "PASS"}
    v = falsify(grid, nulls, conc, miss)
    assert v["O1_PASS"] is False
    assert v["O2_PASS"] is False
    assert v["SIMPLEST_SURVIVING_MODEL"] == "O0"
    assert v["PREDICTIVE_RESEARCH_STOP_RULE"] == "TRIGGERED"
    assert v["PRODUCT_CANDIDATE_STATUS"] == "NO_CANDIDATE"


def test_falsify_managers_dominated_flag():
    grid = {
        "O0": _grid("O0", 0.02, 0.02, 0.02),
        "O1_2Q": _grid("O1", 0.05, 0.05, 0.05),
        "O1_3Q": _grid("O2", 0.05, 0.05, 0.05),
    }
    nulls = {
        "O1_2Q": {"3M": {"exceeds_null_p95": True, "null_p95": 0.02}},
        "O1_3Q": {"3M": {"exceeds_null_p95": True, "null_p95": 0.02}},
    }
    # all leave-one-manager-out medians flip sign vs base -> MANAGER_DOMINATED
    conc = {
        "O1_2Q": {"3M": {"base_median": 0.05, "leave_one_manager_out": {1: -0.01, 2: -0.01, 3: -0.01},
                          "top_securities": [{"count": 1}], "n_obs": 100}},
        "O1_3Q": {"3M": {"base_median": 0.05, "leave_one_manager_out": {1: -0.01},
                          "top_securities": [{"count": 1}], "n_obs": 100}},
    }
    miss = {"MISSINGNESS_GOVERNANCE_STATUS": "PASS"}
    v = falsify(grid, nulls, conc, miss)
    assert "MANAGER_DOMINATED" in v["O1_FAIL_REASONS"]
    assert v["O1_PASS"] is False
