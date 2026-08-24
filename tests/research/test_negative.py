"""Negative tests: the harness must REJECT prohibited behavior."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from thirteenf.research.splits import _hash_bucket, time_split


def test_holdout_rows_cannot_be_reused_as_development():
    periods = [f"2024-Q{i}" for i in range(1, 5)] + [f"2025-Q{i}" for i in range(1, 5)]
    dev, hold = time_split(periods, dev_count=8)
    assert len(hold) == 0  # 8 total -> no holdout; must never overlap
    dev2, hold2 = time_split(periods + ["2025-Q5"], dev_count=8)
    assert set(dev2) & set(hold2) == set()


def test_hash_bucket_is_deterministic():
    assert _hash_bucket("X", "seed", 70) == _hash_bucket("X", "seed", 70)


def test_hash_bucket_never_uses_ticker():
    """Splits must be based on CUSIP/CIK only; ticker is never an input."""
    # _hash_bucket takes a single key; the research layer passes cusip/cik.
    # This test guards the API contract (no ticker parameter exists).
    import inspect

    sig = inspect.signature(_hash_bucket)
    assert "ticker" not in sig.parameters


def test_protocol_file_exists_and_has_freeze_marker():
    protocol = ROOT / "research" / "protocol_v0.1.md"
    assert protocol.exists()
    text = protocol.read_text(encoding="utf-8")
    assert "PROTOCOL_FREEZE_VERSION=v0.1" in text

