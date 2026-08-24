"""Security Semantic Audit tests (v0.2.2). No network, no outcome."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.research.semantic.audit import (
    compute_missingness,
    compute_q1,
    decompose_variant_bias,
    failure_reason,
)
from thirteenf.research.semantic.classifier import classify_cusip
from thirteenf.research.semantic.taxonomy import (
    ClassificationStatus,
    EconomicType,
    is_pooled_issuer,
)


def _of(sec_type="Common Stock", sector="Equity"):
    return [{"securityType": sec_type, "marketSector": sector, "name": "X"}]


def test_common_operating_equity():
    r = classify_cusip("023135106", "AMAZON COM INC", "COM", _of("Common Stock"))
    assert r.economic_type == EconomicType.OPERATING_COMMON_EQUITY.value
    assert r.classification_status == ClassificationStatus.VERIFIED.value


def test_adr():
    r = classify_cusip("874039100", "TAIWAN SEMICONDUCTOR MANUFAC", "SPONSORED ADS", _of("ADR"))
    assert r.economic_type == EconomicType.OPERATING_ADR.value
    assert r.classification_status == ClassificationStatus.VERIFIED.value
    # title-only ADR fallback
    r2 = classify_cusip("X", "SOME CO", "SPON ADS", [])
    assert r2.economic_type == EconomicType.OPERATING_ADR.value
    assert r2.classification_status == ClassificationStatus.PROVISIONAL.value


def test_etf():
    r = classify_cusip("97717Y543", "WISDOMTREE TR", "ARTIFICIAL INTEL", _of("ETP"))
    assert r.economic_type == EconomicType.ETF.value
    assert r.classification_status == ClassificationStatus.VERIFIED.value
    # title-only ETF marker
    r2 = classify_cusip("Y", "SOME TRUST", "ISHARES CORE S&P 500 ETF", [])
    assert r2.economic_type == EconomicType.ETF.value


def test_pooled_fund_and_cef():
    r = classify_cusip("X", "ISHARES TR", "COM", _of("Mutual Fund"))
    assert r.economic_type == EconomicType.MUTUAL_OR_POOLED_FUND.value
    r2 = classify_cusip("X", "SOME FUND", "", _of("Closed-End Fund"))
    assert r2.economic_type == EconomicType.CLOSED_END_FUND.value


def test_unknown_retained():
    r = classify_cusip("X", "SOME OBSCURE ENTITY", "", [])
    assert r.economic_type == EconomicType.UNKNOWN.value
    assert r.classification_status == ClassificationStatus.UNKNOWN.value


def test_conflict_sources():
    # title says ETF but OpenFIGI says Common Stock -> CONFLICT, follows title
    r = classify_cusip("X", "ISHARES TR", "ISHARES CORE S&P 500 ETF", _of("Common Stock"))
    assert r.economic_type == EconomicType.ETF.value
    assert r.classification_status == ClassificationStatus.CONFLICT.value


def test_classification_independent_of_resolution():
    # classify_cusip has no resolution-status input and no ticker input.
    import inspect
    sig = inspect.signature(classify_cusip)
    assert "status" not in sig.parameters
    assert "ticker" not in sig.parameters
    assert "symbol" not in sig.parameters
    assert "resolution" not in sig.parameters
    # unresolved-ticker fund is still classified as pooled
    r = classify_cusip("46436E692", "ISHARES TR", "ESG AWARE 30/70", _of("ETP"))
    assert r.economic_type == EconomicType.ETF.value


def test_outcome_blindness_static_guard():
    import inspect
    import thirteenf.research.semantic.audit as audit
    import thirteenf.research.semantic.classifier as classifier
    for mod in (audit, classifier):
        src = inspect.getsource(mod)
        assert "research.outcomes" not in src
        assert "forward_return" not in src
        assert "null_model" not in src
        assert "benchmark" not in src
        assert "hit_rate" not in src


def test_is_pooled_issuer():
    assert is_pooled_issuer("ISHARES TR")
    assert is_pooled_issuer("SPDR SERIES TRUST")
    assert is_pooled_issuer("MATTHEWS ASIA FDS")
    assert is_pooled_issuer("WISDOMTREE TR")
    assert not is_pooled_issuer("AMAZON COM INC")
    assert not is_pooled_issuer("ALPHABET INC")


def test_composition_reconciles():
    class_df = pd.DataFrame(
        {
            "cusip": ["A", "B", "C"],
            "economic_type": ["OPERATING_COMMON_EQUITY", "ETF", "UNKNOWN"],
            "classification_status": ["VERIFIED", "VERIFIED", "UNKNOWN"],
        }
    )
    frames = {
        "O0": pd.DataFrame(
            {
                "cusip": ["A", "A", "B", "C"],
                "info_date": ["2024-01-01"] * 4,
                "part": ["H0_dev"] * 4,
                "activity": ["positive"] * 4,
                "change_type": ["ADD"] * 4,
            }
        ),
        "O1_2Q": pd.DataFrame(
            {
                "cusip": ["A"],
                "info_date": ["2024-01-01"],
                "part": ["H0_dev"],
                "activity": ["positive"],
                "change_type": ["ADD"],
            }
        ),
        "O1_3Q": pd.DataFrame(
            {
                "cusip": [],
                "info_date": [],
                "part": [],
                "activity": [],
                "change_type": [],
            }
        ),
    }
    q1 = compute_q1(class_df, frames)
    assert q1["security_total"] == 3
    assert q1["observation_total"] == 4


def test_failure_reason_deterministic():
    assert failure_reason("UNRESOLVED", "", "ETF") == "FUND_OR_ETF_IDENTITY_PATH_MISSING"
    assert failure_reason("UNRESOLVED", "no US venue record", "OPERATING_COMMON_EQUITY") == "DELISTED_OR_TERMINATED"
    assert failure_reason("UNRESOLVED", "no SEC issuer corroboration", "OPERATING_COMMON_EQUITY") == "SEC_CORROBORATION_MISSING"
    assert failure_reason("CONFLICT", "SEC unique ticker X != OpenFIGI Y", "X") == "NAME_OR_ENTITY_CONFLICT"
    assert failure_reason("CONFLICT", "OpenFIGI securityType=ADR but 13F title", "X") == "ADR_OR_ORDINARY_AMBIGUITY"
    assert failure_reason("AMBIGUOUS", "multiple distinct US tickers", "X") == "OPENFIGI_MULTI_MATCH"
    assert failure_reason("NON_EQUITY_OR_UNSUPPORTED", "", "X") == "NON_EQUITY"


def test_variant_bias_decomposition_and_missingness():
    frames = {
        v: pd.DataFrame(
            {
                "cusip": ["A", "B", "C"],
                "manager_id": [1, 1, 1],
                "security_id": [10, 20, 30],
                "report_period": ["2024-01-01"] * 3,
                "info_date": ["2024-01-01"] * 3,
                "part": ["H0_dev"] * 3,
                "activity": ["positive", "negative", "positive"],
                "change_type": ["ADD", "REDUCE", "ADD"],
            }
        )
        for v in ("O0", "O1_2Q", "O1_3Q")
    }
    master = pd.DataFrame(
        [
            {"cusip": "A", "status": "VERIFIED_EXACT", "symbol": "AAA"},
            {"cusip": "B", "status": "UNRESOLVED", "symbol": ""},
            {"cusip": "C", "status": "VERIFIED_EXACT", "symbol": "CCC"},
        ]
    )
    avail = pd.DataFrame(
        [
            {"symbol": "AAA", "first_trade_date": "2020-01-01"},
            {"symbol": "CCC", "first_trade_date": "2025-01-01"},
        ]
    )
    class_df = pd.DataFrame(
        {
            "cusip": ["A", "B", "C"],
            "economic_type": ["OPERATING_COMMON_EQUITY", "ETF", "OPERATING_COMMON_EQUITY"],
            "classification_status": ["VERIFIED", "VERIFIED", "VERIFIED"],
        }
    )
    vbd = decompose_variant_bias(frames, master, avail, class_df)
    assert vbd["O0"]["overall"] == 33.333  # A covered, B not verified, C start>info
    miss = compute_missingness(frames, master, avail, class_df)
    assert miss["overall"]["unmapped_observations"] == 1  # C only (operating set)
    assert miss["overall"]["OPERATING_EQUITY_MISSINGNESS_STATUS"] in (
        "LOW_CONCERN", "MODERATE_CONCERN", "HIGH_CONCERN",
    )
