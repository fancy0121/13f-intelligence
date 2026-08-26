from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from store import get_store


def run() -> None:
    st.subheader("我的组合 - 持仓事实交叉验证")
    st.caption("本页只展示与你持仓相关的已披露事实（含增持、减持、退出、陈旧、质量），"
               "不做任何买卖建议，也不推断你的投资论点。")
    store = get_store()
    portfolio_path = ROOT / "config" / "portfolio.csv"
    out = store.portfolio_evidence(portfolio_path)
    if out == "SETUP_REQUIRED":
        st.warning("SETUP_REQUIRED：config/portfolio.csv 为空或不存在。请在文件中填写 ticker,weight 后重试。"
                   "系统不会生成演示组合。")
        return

    st.dataframe(
        [
            {
                "Ticker": r["ticker"],
                "权重": r["weight"],
                "状态": r["status"],
                "持有机构实体数": r["holder_entity_count"],
                "独立增持": r["independent_add_manager_count"],
                "独立减持": r["independent_reduce_manager_count"],
                "独立退出": r["independent_exit_manager_count"],
                "独立新增": r["independent_new_manager_count"],
                "重复增持(≥2Q)": r["repeated_add_manager_count"],
                "重复减持(≥2Q)": r["repeated_reduce_manager_count"],
                "活动状态": r["activity_state"],
                "数据距今(天)": r["days_since_filing"],
                "解析状态": r["resolution_status"],
            }
            for r in out
        ],
        width='stretch',
    )
    st.caption("对称规则：增持/减持/退出同权重展示；缺失一侧显示 0；不突出任何单一方向。")


run()
