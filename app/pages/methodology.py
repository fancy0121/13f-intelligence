from __future__ import annotations

from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "product_methodology_and_limitations.md"


def run() -> None:
    st.subheader("方法论与限制")
    if DOC.exists():
        st.markdown(DOC.read_text(encoding="utf-8"))
    else:
        st.info("方法论文档缺失。")


run()

