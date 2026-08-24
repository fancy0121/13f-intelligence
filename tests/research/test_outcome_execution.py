"""Frozen outcome execution tests (synthetic, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.research.outcomes.execution import (
    HORIZONS_DAYS,
    attach_returns,
    concentration_audit,
    evaluate_grid,
    run_null,
)


def _frame(n=20, part="H0_dev"):
    return pd.DataFrame(
        {
            "cusip": ["A"] * n,
            "security_id": [10] * n,
            "manager_id": [i % 4 for i in range(n)],
            "report_period": ["2024-01-01"] * n,
            "info_date": ["2024-01-02"] * n,
            "part": [part] * n,
            "activity": ["positive"] * n,
            "change_type": ["ADD"] * n,
        }
    )


def _prices(start="2024-01-02", n=300, base=100.0):
    import datetime

    dates = []
    d = datetime.date.fromisoformat(start)
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return {"dates": dates, "adjclose": [base + i for i in range(n)], "splits": {}, "error": None}


def test_attach_returns_and_grid():
    frames = {"O0": _frame(20), "O1_2Q": _frame(10)}
    price_map = {"AAA": _prices()}
    bench = _prices(base=100.0)
    datasets = attach_returns(frames, {"A": "AAA"}, price_map, bench)
    assert datasets["O0"]["ret_3M"].notna().sum() == 20
    assert datasets["O0"]["excess_12M"].notna().sum() == 20
    grid = evaluate_grid(datasets)
    assert grid["O0"]["H0_dev"]["3M"]["n_ret"] == 20
    assert "median" in grid["O0"]["H0_dev"]["3M"]


def test_right_censoring_marked():
    frames = {"O0": _frame(5)}
    # short series: 100 bars, info date at start -> 12M (252) censored
    price_map = {"AAA": _prices(n=100)}
    datasets = attach_returns(frames, {"A": "AAA"}, price_map, {})
    assert int(datasets["O0"]["censored_12M"].sum()) == 5
    assert int(datasets["O0"]["censored_3M"].sum()) == 0


def test_null_deterministic_and_rule():
    frames = {"O0": _frame(100), "O1_2Q": _frame(50)}
    price_map = {"AAA": _prices()}
    datasets = attach_returns(frames, {"A": "AAA"}, price_map, _prices())
    n1 = run_null(datasets, "O0", "3M")
    n2 = run_null(datasets, "O0", "3M")
    assert n1["observed_median"] == n2["observed_median"]
    assert n1["null_p95"] == n2["null_p95"]
    assert n1["seed"] == "13f-outcome-v0.2-null"


def test_concentration_audit_shape():
    frames = {"O0": _frame(40)}
    datasets = attach_returns(frames, {"A": "AAA"}, {"AAA": _prices()}, _prices())
    c = concentration_audit(datasets, "O0", "3M")
    assert "leave_one_manager_out" in c
    assert "top_securities" in c
    assert "time_regime_median" in c


def test_horizons_frozen():
    assert HORIZONS_DAYS == {"3M": 63, "6M": 126, "12M": 252}

