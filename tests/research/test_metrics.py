from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.research.metrics import coverage, leave_one_manager_out, sign_stability
from thirteenf.research.experiments import a0_signals


def _obs():
    return pd.DataFrame(
        [
            {"security_id": 1, "cusip": "A", "manager_id": 1,
             "report_period": "2025-03-31", "change_type": "ADD",
             "shares_prev": 1, "shares_now": 2, "weight_prev": 0.1,
             "weight_now": 0.2, "weight_change": 0.1, "info_date": "d"},
            {"security_id": 1, "cusip": "A", "manager_id": 1,
             "report_period": "2025-06-30", "change_type": "ADD",
             "shares_prev": 2, "shares_now": 3, "weight_prev": 0.2,
             "weight_now": 0.3, "weight_change": 0.1, "info_date": "d"},
            {"security_id": 2, "cusip": "B", "manager_id": 2,
             "report_period": "2025-03-31", "change_type": "REDUCE",
             "shares_prev": 5, "shares_now": 1, "weight_prev": 0.4,
             "weight_now": 0.1, "weight_change": -0.3, "info_date": "d"},
        ]
    )


def test_coverage_counts():
    sig = a0_signals(_obs())
    cov = coverage(sig)
    assert cov["eligible"] == 3
    assert cov["signal_producing"] == 3
    assert cov["security_coverage"] == 2
    assert cov["quarter_coverage"] == 2


def test_sign_stability():
    sig = a0_signals(_obs())
    stab = sign_stability(sig, "net_directional")
    assert stab["n_pairs"] == 1
    assert stab["stability"] == 1.0


def test_leave_one_manager_out_runs():
    obs = _obs()
    dom = leave_one_manager_out(obs, a0_signals, "net_directional")
    assert "flip_fraction" in dom
    assert dom["n_comparisons"] >= 0
