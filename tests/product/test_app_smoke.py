"""Streamlit page smoke tests (Gate: pages render without exception)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytest.importorskip("streamlit.testing")

from streamlit.testing.v1 import AppTest


def _run(page: str):
    at = AppTest.from_file(str(ROOT / "app" / "pages" / page), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def test_overview_page_smoke():
    at = _run("overview.py")
    assert any(m.label.startswith("最新报告季度") for m in at.metric)


def test_managers_page_smoke():
    at = _run("managers.py")
    assert any(t.label.startswith("选择机构") for t in at.text_input)


def test_securities_page_smoke():
    at = _run("securities.py")
    assert any(t.label.startswith("输入 Ticker") for t in at.text_input)


def test_activity_page_smoke():
    at = _run("activity.py")
    assert any(t.label.startswith("排序指标") for t in at.text_input)


def test_portfolio_page_smoke():
    at = _run("portfolio.py")
    # empty portfolio must show SETUP_REQUIRED and no exception
    assert not at.exception


def test_methodology_page_smoke():
    at = _run("methodology.py")
    assert not at.exception


def test_observation_page_smoke():
    at = _run("observation.py")
    assert not at.exception
    assert any(w.value.startswith("INSUFFICIENT_OBSERVATION") for w in at.warning)
