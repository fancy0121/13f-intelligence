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

from store import configured_database_path, database_validation_error, public_snapshot_error, public_validation_scope
from ui import BRAND_HTML, FOOTER_HTML, T, inject_style

st.set_page_config(
    page_title="13F 机构持仓情报系统 / 13F Institutional Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    with public_validation_scope():
        _render_main()


def _render_main() -> None:
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

    pages = [
        st.Page(ROOT / "app" / "views" / "overview.py", title=T("总览", "Overview"), default=True),
        st.Page(ROOT / "app" / "views" / "managers.py", title=T("机构", "Managers")),
        st.Page(ROOT / "app" / "views" / "securities.py", title=T("证券", "Securities")),
        st.Page(ROOT / "app" / "views" / "activity.py", title=T("活动探索", "Activity")),
        st.Page(ROOT / "app" / "views" / "portfolio.py", title=T("我的组合", "My Portfolio")),
        st.Page(ROOT / "app" / "views" / "methodology.py", title=T("方法论与限制", "Methodology")),
        st.Page(ROOT / "app" / "views" / "observation.py", title=T("研究观察", "Research Log")),
    ]
    # Keep views outside the legacy pages directory so cold-start deep links
    # always execute this shared entrypoint. Register routes before st.stop.
    pg = st.navigation(pages)
    validation_error = database_validation_error(configured_database_path())
    if validation_error:
        st.error(T(
            "数据库需重建：当前数据快照尚未验证，页面已停止。 [NOT_VALIDATED]",
            "Database rebuild required: the current data snapshot is not validated; pages are stopped. [NOT_VALIDATED]",
        ))
        st.caption(validation_error)
        st.stop()
    release_error = public_snapshot_error()
    if release_error:
        st.error(T(
            "发布证据缺失或不匹配：公开页面已停止，请联系维护人员。 [NOT_VALIDATED]",
            "Release evidence is missing or mismatched; public pages are stopped. Contact the maintainer. [NOT_VALIDATED]",
        ))
        st.caption(release_error)
        st.stop()
    pg.run()
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
