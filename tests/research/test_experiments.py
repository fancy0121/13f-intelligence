from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.research.experiments import (
    a0_signals,
    a1_signals,
    a2_signals,
    a3_stratified,
    bucket_managers,
)


def _obs():
    return pd.DataFrame(
        [
            # security 1: manager 1 adds twice in a row (persistence 2Q)
            {"security_id": 1, "cusip": "AAAA11111", "manager_id": 10,
             "report_period": "2025-03-31", "change_type": "ADD",
             "shares_prev": 100, "shares_now": 200,
             "weight_prev": 0.1, "weight_now": 0.2, "weight_change": 0.1,
             "info_date": "2025-05-15"},
            {"security_id": 1, "cusip": "AAAA11111", "manager_id": 10,
             "report_period": "2025-06-30", "change_type": "ADD",
             "shares_prev": 200, "shares_now": 300,
             "weight_prev": 0.2, "weight_now": 0.25, "weight_change": 0.05,
             "info_date": "2025-08-14"},
            # security 2: manager 20 exits (weight down)
            {"security_id": 2, "cusip": "BBBB22222", "manager_id": 20,
             "report_period": "2025-06-30", "change_type": "EXIT",
             "shares_prev": 50, "shares_now": None,
             "weight_prev": 0.05, "weight_now": None, "weight_change": None,
             "info_date": "2025-08-14"},
            # security 3: shares up but weight down (divergence)
            {"security_id": 3, "cusip": "CCCC33333", "manager_id": 30,
             "report_period": "2025-06-30", "change_type": "ADD",
             "shares_prev": 10, "shares_now": 20,
             "weight_prev": 0.5, "weight_now": 0.3, "weight_change": -0.2,
             "info_date": "2025-08-14"},
        ]
    )


def test_a0_counts_net_directional():
    out = a0_signals(_obs())
    row = out[out["security_id"] == 1].iloc[0]
    assert row["eligible"] == 1
    assert row["ADD"] == 1
    assert row["net_directional"] == 1
    row3 = out[out["security_id"] == 3].iloc[0]
    assert row3["net_directional"] == 1  # A0 ignores weight


def test_a1_persistence_filters():
    out = a1_signals(_obs(), k=2)
    # security 1 manager has 2 consecutive ADD -> present; security 3 only 1 -> absent
    assert (out["security_id"] == 1).any()
    assert not (out["security_id"] == 3).any()


def test_a2_detects_shares_up_weight_down():
    out = a2_signals(_obs())
    row = out[out["security_id"] == 3].iloc[0]
    assert row["UP_DOWN"] == 1
    assert row["net_weight_direction"] == 0
    assert row["divergence_rate"] == 1.0


def test_a2_counts_exit_negative():
    out = a2_signals(_obs())
    row = out[out["security_id"] == 2].iloc[0]
    assert row["EXIT"] == 1
    assert row["net_weight_direction"] == -1


def test_bucket_managers_deterministic_quantiles():
    chars = pd.DataFrame(
        {
            "manager_id": [1, 2, 3, 4, 5, 6],
            "filing_continuity": [12, 12, 12, 12, 12, 3],
            "avg_concentration": [0.1, 0.2, 0.3, 0.4, 0.5, 0.9],
        }
    )
    b1 = bucket_managers(chars, "filing_continuity", n_buckets=3)
    b2 = bucket_managers(chars, "filing_continuity", n_buckets=3)
    assert b1 == b2
    assert b1[6] == "LOW"
    assert set(b1.values()) <= {"LOW", "MEDIUM", "HIGH"}


def test_a3_stratified_returns_buckets():
    obs = _obs()
    chars = pd.DataFrame(
        {
            "manager_id": [10, 20, 30],
            "filing_continuity": [12, 12, 3],
            "avg_concentration": [0.3, 0.4, 0.9],
            "avg_position_count": [50, 50, 5],
            "options_proxy": [0.01, 0.01, 0.0],
        }
    )
    out = a3_stratified(obs, chars, feature="filing_continuity")
    assert set(out.keys()) <= {"LOW", "MEDIUM", "HIGH"}
    assert len(out) >= 1
