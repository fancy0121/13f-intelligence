"""13F Institutional Intelligence System - Streamlit UI (evidence only, v0.5.1)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from ui import BRAND_HTML, FOOTER_HTML, T, inject_style

st.set_page_config(
    page_title="13F 机构持仓情报系统 / 13F Institutional Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    inject_style()
    with st.sidebar:
        st.markdown(BRAND_HTML, unsafe_allow_html=True)
        st.markdown(
            "基于 **SEC Form 13F** 原始披露的机构持仓证据系统。\n\n"
            "Evidence-only · 不含投资建议 · 不产生预测信号。\n\n"
            "Built on **SEC Form 13F** original filings. Evidence only - no "
            "investment advice, no forward-looking conclusions."
        )
        st.divider()

    st.title(T("13F 机构持仓情报系统", "13F Institutional Intelligence System"))
    st.caption(
        T(
            "基于 SEC Form 13F 原始披露的结构化、可验证、可追溯的机构持仓行为证据。"
            "本系统只展示已披露事实与数据质量，不提供投资建议，不产生任何预测性信号。",
            "Structured, verifiable, traceable institutional holding evidence from SEC "
            "Form 13F filings. This system shows disclosed facts and data quality only - "
            "no investment advice, no forward-looking conclusions.",
        )
    )

    if not (ROOT / "data" / "thirteenf.db").exists():
        st.error(T("数据库不存在。请先运行数据构建后重试。", "Database not found. Please build the data first."))
        st.stop()

    pages = [
        st.Page("pages/overview.py", title=T("总览", "Overview"), default=True),
        st.Page("pages/managers.py", title=T("机构", "Managers")),
        st.Page("pages/securities.py", title=T("证券", "Securities")),
        st.Page("pages/activity.py", title=T("活动探索", "Activity")),
        st.Page("pages/portfolio.py", title=T("我的组合", "My Portfolio")),
        st.Page("pages/methodology.py", title=T("方法论与限制", "Methodology")),
        st.Page("pages/observation.py", title=T("研究观察", "Research Log")),
    ]
    pg = st.navigation(pages)
    pg.run()
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
