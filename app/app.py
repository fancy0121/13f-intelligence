"""13F Institutional Intelligence System - Streamlit UI (Chinese)."""

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

import db  # noqa: E402  (app-local module)


def main() -> None:
    st.title("13F 机构持仓情报系统")
    st.caption(
        "基于 SEC Form 13F 原始披露的结构化、可验证、可追溯的机构持仓行为证据。"
        "本系统不提供投资建议，不产生买卖信号。"
    )

    if not db.db_ready():
        st.error(
            "数据库不存在。请先运行数据构建："
            "`python -m thirteenf.cli normalize` 与 `python -m thirteenf.cli analyze`。"
        )
        st.stop()

    pages = [
        st.Page("pages/overview.py", title="总览", default=True),
        st.Page("pages/managers.py", title="机构"),
        st.Page("pages/stocks.py", title="个股"),
        st.Page("pages/consensus.py", title="共识"),
        st.Page("pages/portfolio.py", title="我的组合"),
    ]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()

