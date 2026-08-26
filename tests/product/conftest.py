"""Product test fixtures (read-only real DB + committed artifacts)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.evidence import ProductStore


@pytest.fixture(scope="session")
def store():
    s = ProductStore(
        ROOT / "data" / "thirteenf.db",
        ROOT / "reports" / "research" / "security_resolution_master.csv",
        ROOT / "reports" / "research" / "security_semantic_classification.csv",
        ROOT / "config" / "managers.csv",
    )
    yield s
    s.close()


@pytest.fixture(scope="session")
def repo_root():
    return ROOT

