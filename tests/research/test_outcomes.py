"""Outcome adapter tests (no network; fixtures only)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.research.outcomes.null_model import permute_signals, seeded_rng
from thirteenf.research.outcomes.returns import (
    first_trading_day_after,
    forward_return,
)
from thirteenf.research.outcomes.symbols import (
    SymbolMapping,
    load_symbol_mappings,
    resolve,
)


def test_first_trading_day_after():
    dates = ["2026-08-13", "2026-08-14", "2026-08-17", "2026-08-18"]
    assert first_trading_day_after(dates, "2026-08-14") == 1
    assert first_trading_day_after(dates, "2026-08-15") == 2  # next trading day
    assert first_trading_day_after(dates, "2026-08-19") is None


def test_forward_return_3m():
    dates = [f"2026-08-{d:02d}" for d in range(13, 26)]
    adjclose = [100.0 + i for i in range(len(dates))]
    r = forward_return(dates, adjclose, "2026-08-13", 3)
    assert r is not None
    assert abs(r - (103.0 / 100.0 - 1.0)) < 1e-9


def test_forward_return_insufficient():
    dates = ["2026-08-13", "2026-08-14"]
    adjclose = [100.0, 101.0]
    assert forward_return(dates, adjclose, "2026-08-13", 12) is None


def test_forward_return_null_price():
    dates = ["2026-08-13", "2026-08-14", "2026-08-17", "2026-08-18"]
    adjclose = [100.0, None, 102.0, 103.0]
    assert forward_return(dates, adjclose, "2026-08-13", 1) is None


def test_symbol_mapping_only_curated(tmp_path):
    p = tmp_path / "symbols.csv"
    p.write_text(
        "cusip,symbol,exchange,source,effective_date,verified_at,verified_by,notes\n"
        "037833100,AAPL,NMS,MANUAL_REVIEW,2021-01-01,2026-08-24,ASUS,\n",
        encoding="utf-8",
    )
    mappings = load_symbol_mappings(p)
    m = resolve(mappings, "037833100")
    assert isinstance(m, SymbolMapping)
    assert m.symbol == "AAPL"
    assert resolve(mappings, "999999999") is None


def test_symbol_mapping_empty_file(tmp_path):
    p = tmp_path / "symbols.csv"
    p.write_text("cusip,symbol\n", encoding="utf-8")
    assert load_symbol_mappings(p) == {}


def test_null_permutation_preserves_structure_and_seed():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    groups = ["g1", "g1", "g1", "g2", "g2", "g2"]
    r1 = seeded_rng()
    a = permute_signals(values, groups, r1)
    r2 = seeded_rng()
    b = permute_signals(values, groups, r2)
    assert a == b  # deterministic same seed
    # structure preserved: group sums unchanged
    assert sum(a[:3]) == sum(values[:3])
    assert sum(a[3:]) == sum(values[3:])
    # not trivially identical
    assert a != values


def test_null_permutation_different_seed_differs():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    groups = ["g1", "g1", "g1", "g2", "g2", "g2"]
    r1 = random.Random("seed-a")
    r2 = random.Random("seed-b")
    a = permute_signals(values, groups, r1)
    b = permute_signals(values, groups, r2)
    assert a != b


import random  # noqa: E402

