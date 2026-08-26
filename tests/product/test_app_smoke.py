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
    assert any(m.label == "最新报告季度" for m in at.metric)


def test_managers_page_smoke():
    at = _run("managers.py")
    assert any(s.label == "选择机构" for s in at.selectbox)


def test_securities_page_smoke():
    at = _run("securities.py")
    assert any(t.label == "输入 Ticker / CUSIP / 机构名（发行方）查询" for t in at.text_input)


def test_activity_page_smoke():
    at = _run("activity.py")
    assert any(s.label == "排序指标" for s in at.selectbox)


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
    assert any(w.value == "INSUFFICIENT_OBSERVATION — 尚无足够的真实使用 episode，"
               "当前不给出任何真实世界效用结论。" for w in at.warning)
