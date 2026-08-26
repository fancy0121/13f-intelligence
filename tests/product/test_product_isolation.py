"""Predictive isolation static guards (Gate P3)."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

FORBIDDEN_WORDS = (
    "bullish", "bearish", "conviction", "high confidence", "opportunity",
    "smart money", "buy", "sell", "predictive", "alpha", "signal",
    "consensus_score", "trend_label", "scoring_status", "signal_quality",
    "supportive thesis", "contrary thesis",
)


def test_product_modules_do_not_import_outcomes():
    import thirteenf.product
    import thirteenf.product.evidence as evidence
    import thirteenf.product.tasks as tasks
    for mod in (thirteenf.product, evidence, tasks):
        src = inspect.getsource(mod)
        assert "research.outcomes" not in src
        assert "null_model" not in src
        assert "falsif" not in src.lower()
        assert "forward_return" not in src


def test_product_code_has_no_forbidden_language():
    import thirteenf.product
    import thirteenf.product.evidence as evidence
    import thirteenf.product.tasks as tasks
    for mod in (thirteenf.product, evidence, tasks):
        src = inspect.getsource(mod).lower()
        for w in FORBIDDEN_WORDS:
            assert w not in src, f"forbidden word in product module: {w}"


def test_ui_docs_language_policy():
    # product governance docs explain forbidden words; they may contain them
    # in the Forbidden list, so only check product code + app pages.
    app_dir = ROOT / "app"
    for p in app_dir.rglob("*.py"):
        text = p.read_text(encoding="utf-8").lower()
        for w in ("bullish", "bearish", "conviction", "smart money",
                  "consensus_score", "scoring_status", "signal_quality",
                  "trend_label", "buy", "sell", "opportunity", "alpha",
                  "predictive", "signal"):
            assert w not in text, f"forbidden word in {p}: {w}"
