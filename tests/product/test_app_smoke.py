"""Streamlit page smoke tests (Gate: pages render without exception)."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytest.importorskip("streamlit.testing")

from streamlit.testing.v1 import AppTest

if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from ui import B


def _run(page: str):
    at = AppTest.from_file(str(ROOT / "app" / "pages" / page), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def test_bilingual_sentence_has_no_duplicate_terminal_punctuation():
    assert B("中文句子。", "English sentence.") == "中文句子。English sentence."


def test_overview_page_smoke():
    at = _run("overview.py")
    assert any(m.label.startswith("最新报告季度") for m in at.metric)


def test_overview_quality_codes_are_bilingual():
    at = _run("overview.py")
    visible = "\n".join(str(m.value) for m in at.markdown)
    assert "季度不完整 / Incomplete quarter [INCOMPLETE_QUARTER]" in visible


def test_overview_long_metric_values_use_compact_display():
    at = _run("overview.py")
    metrics = {m.label: str(m.value) for m in at.metric}
    assert re.fullmatch(r"\d+\.\d%", metrics["已解析证券覆盖 / Resolved Coverage"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", metrics["本地数据更新 / Local Data Updated"])


def test_managers_page_smoke():
    at = _run("managers.py")
    assert any(t.label.startswith("选择机构") for t in at.text_input)


def test_managers_page_renders_exit_rows_without_crashing():
    """Regression: EXIT rows have shares_now=None and must still render."""
    at = _run("managers.py")
    at.text_input[0].set_value("Berkshire")
    at.run()
    assert len(at.button) == 1
    at.button[0].click()
    at.run()
    assert not at.exception, at.exception
    assert any(m.label.startswith("报告季度") for m in at.metric)
    visible = "\n".join(str(m.value) for m in at.markdown)
    assert "退出 / EXIT" in visible
    assert any(
        "已验证 / Verified [VERIFIED]" in str(c.value)
        for c in at.caption
    )


def test_manager_weight_pairs_are_human_readable():
    at = _run("managers.py")
    at.text_input[0].set_value("Berkshire")
    at.run()
    frames = [frame.value for frame in at.dataframe]
    weight_columns = [
        column
        for frame in frames
        for column in frame.columns
        if str(column).startswith("权重(前/后)")
    ]
    assert weight_columns
    for frame in frames:
        for column in weight_columns:
            if column not in frame.columns:
                continue
            values = " ".join(str(v) for v in frame[column])
            assert "None" not in values
            assert "e-" not in values.lower()


def test_manager_unique_keyboard_query_selects_without_click():
    """A unique typed query must be usable without a mouse-only candidate click."""
    at = _run("managers.py")
    at.text_input[0].set_value("Berkshire")
    at.run()
    assert not at.exception, at.exception
    assert any(m.label.startswith("报告季度") for m in at.metric)


def test_manager_selector_displays_chinese_and_english_names():
    at = _run("managers.py")
    labels = [b.label for b in at.button]
    assert "伯克希尔·哈撒韦 / BERKSHIRE HATHAWAY INC" in labels
    assert len(labels) == 29
    assert all("中文名待核验" not in label for label in labels)


def test_every_tracked_manager_detail_renders_without_exception():
    at = _run("managers.py")
    manager_labels = [b.label for b in at.button]
    for label in manager_labels:
        at.text_input[0].set_value(label)
        at.run()
        assert not at.exception, f"{label}: {at.exception}"
        assert any(m.label.startswith("报告季度") for m in at.metric), label


def test_securities_page_smoke():
    at = _run("securities.py")
    assert any(t.label.startswith("输入 Ticker") for t in at.text_input)


def test_security_search_accepts_chinese_company_name():
    at = _run("securities.py")
    at.text_input[0].set_value("字母表")
    at.run()
    labels = [b.label for b in at.button]
    assert any("字母表公司 / ALPHABET INC" in label for label in labels)


def test_security_candidate_marks_missing_chinese_name_explicitly():
    at = _run("securities.py")
    at.text_input[0].set_value("1 800 FLOWERS")
    at.run()
    visible = "\n".join(str(m.value) for m in at.markdown)
    assert "中文名待核验 / 1 800 FLOWERS COM INC" in visible


def test_single_security_match_opens_with_bilingual_status_without_extra_click():
    at = _run("securities.py")
    at.text_input[0].set_value("GOOGL")
    at.run()
    assert not at.exception, at.exception
    metrics = {m.label: str(m.value) for m in at.metric}
    assert metrics["股票代码 / Ticker"] == "GOOGL"
    assert "解析状态 / Resolution" not in metrics
    assert "经济类型 / Economic Type" not in metrics
    visible = "\n".join(str(m.value) for m in at.markdown)
    assert "解析状态 / Resolution：精确验证 / Verified exact" in visible
    assert "经济类型 / Economic Type：经营性普通股 / Operating common equity" in visible
    assert {"新增 / NEW", "增持 / ADD", "减持 / REDUCE", "退出 / EXIT", "未变化 / UNCHANGED"} <= set(metrics)


def test_security_status_and_economic_type_samples_render_without_exception():
    samples: set[str] = set()
    for relative, field in (
        ("reports/research/security_resolution_master.csv", "status"),
        ("reports/research/security_semantic_classification.csv", "economic_type"),
    ):
        seen: set[str] = set()
        with (ROOT / relative).open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                value = row.get(field, "")
                if value and value not in seen:
                    samples.add(row["cusip"])
                    seen.add(value)

    at = _run("securities.py")
    for cusip in sorted(samples):
        at.text_input[0].set_value(cusip)
        at.run()
        assert not at.exception, f"{cusip}: {at.exception}"
        visible = "\n".join(str(m.value) for m in at.markdown)
        assert "解析状态 / Resolution：" in visible, cusip
        assert "经济类型 / Economic Type：" in visible, cusip


def test_activity_page_smoke():
    at = _run("activity.py")
    assert any(t.label.startswith("排序指标") for t in at.text_input)


def test_activity_keyboard_selection_has_bilingual_table_columns():
    at = _run("activity.py")
    at.text_input[0].set_value("Independent ADD")
    at.run()
    assert not at.exception, at.exception
    columns = set(at.dataframe[0].value.columns)
    assert {
        "独立新增 / Independent NEW",
        "独立增持 / Independent ADD",
        "独立减持 / Independent REDUCE",
        "独立退出 / Independent EXIT",
        "重复增持 / Repeated ADD",
        "重复减持 / Repeated REDUCE",
    } <= columns


def test_every_activity_metric_renders_without_exception():
    at = _run("activity.py")
    metric_labels = [b.label for b in at.button]
    for label in metric_labels:
        at.text_input[0].set_value(label)
        at.run()
        assert not at.exception, f"{label}: {at.exception}"
        assert at.dataframe, label


def test_portfolio_page_smoke():
    at = _run("portfolio.py")
    # empty portfolio must show SETUP_REQUIRED and no exception
    assert not at.exception


def test_methodology_page_smoke():
    at = _run("methodology.py")
    assert not at.exception


def test_methodology_page_does_not_render_raw_html_tags():
    at = _run("methodology.py")
    visible_markdown = "\n".join(str(m.value) for m in at.markdown)
    assert "<span" not in visible_markdown


def test_observation_page_smoke():
    at = _run("observation.py")
    assert not at.exception
    assert any(w.value.startswith("INSUFFICIENT_OBSERVATION") for w in at.warning)


def test_observation_exports_are_real_browser_downloads():
    at = _run("observation.py")
    downloads = at.get("download_button")
    assert len(downloads) == 2
    assert {d.label for d in downloads} == {
        "下载 CSV / Download CSV",
        "下载 JSON / Download JSON",
    }


def test_observation_summary_uses_bilingual_human_readable_labels():
    at = _run("observation.py")
    visible = "\n".join(str(m.value) for m in at.markdown)
    assert "证券 / Security: 0" in visible
    assert "熟悉 / Familiar: 0" in visible
    assert "无风险 / None [NONE]: 0" in visible
    assert "{'security':" not in visible
