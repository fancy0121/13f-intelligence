"""13F Institutional Intelligence System - Streamlit UI (evidence only, v0.4)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

st.set_page_config(
    page_title="13F 机构持仓情报系统",
    page_icon="📊",
    layout="wide",
)


def main() -> None:
    st.title("13F 机构持仓情报系统")
    st.caption(
        "基于 SEC Form 13F 原始披露的结构化、可验证、可追溯的机构持仓行为证据。"
        "本系统只展示已披露事实与数据质量，不提供投资建议，不产生任何预测性信号。"
    )

    if not (Path(__file__).resolve().parents[1] / "data" / "thirteenf.db").exists():
        st.error(
            "数据库不存在。请先运行数据构建后重试。"
        )
        st.stop()

    pages = [
        st.Page("pages/overview.py", title="总览", default=True),
        st.Page("pages/managers.py", title="机构"),
        st.Page("pages/securities.py", title="证券"),
        st.Page("pages/activity.py", title="活动探索"),
        st.Page("pages/portfolio.py", title="我的组合"),
        st.Page("pages/methodology.py", title="方法论与限制"),
    ]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
