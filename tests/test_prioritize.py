from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from prioritize_unresolved import load_portfolio_tickers


def test_load_portfolio_tickers_empty(tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text("# header\nticker,weight\n", encoding="utf-8")
    assert load_portfolio_tickers(p) == []


def test_load_portfolio_tickers_parses():
    p = ROOT / "config" / "portfolio.csv"
    if p.exists():
        assert isinstance(load_portfolio_tickers(p), list)


def test_load_portfolio_tickers_uppercases(tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text("ticker,weight\naapl,0.1\nMSFT,\n", encoding="utf-8")
    assert load_portfolio_tickers(p) == ["AAPL", "MSFT"]

