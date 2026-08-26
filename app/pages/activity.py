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


METRICS = {
    "独立机构新增计数 (NEW)": "independent_new_manager_count",
    "独立机构增持计数 (ADD)": "independent_add_manager_count",
    "独立机构减持计数 (REDUCE)": "independent_reduce_manager_count",
    "独立机构退出计数 (EXIT)": "independent_exit_manager_count",
    "重复增持计数 (≥2Q ADD)": "repeated_add_manager_count",
    "重复减持计数 (≥2Q REDUCE)": "repeated_reduce_manager_count",
    "持有机构实体数": "holder_entity_count",
}


def run() -> None:
    st.subheader("活动探索 - 描述性排序（非推荐榜）")
    store = get_store()
    metric_label = st.selectbox("排序指标", list(METRICS))
    rows = store.activity_explorer(METRICS[metric_label], limit=100)
    st.caption(
        "说明：计数为最新报告季度内“已验证独立机构”的动作数量；重复计数为连续 ≥2 个报告季度同方向（缺失季度中断）。"
        "身份未验证/未解析证券仍会显示其解析状态，不做隐藏过滤。"
        "该页仅为中性事实排序，不构成任何“最佳/机会”含义。"
    )
    if not rows:
        st.info("INSUFFICIENT_DATA。")
        return
    st.dataframe(
        [
            {
                "Ticker": r["ticker"] or r["cusip"],
                "CUSIP": r["cusip"],
                "Issuer": r["issuer"],
                "解析状态": r["resolution_status"],
                "经济类型": r["economic_type"],
                "持有机构实体数": r["holder_entity_count"],
                "独立NEW": r["independent_new_manager_count"],
                "独立ADD": r["independent_add_manager_count"],
                "独立REDUCE": r["independent_reduce_manager_count"],
                "独立EXIT": r["independent_exit_manager_count"],
                "重复ADD": r["repeated_add_manager_count"],
                "重复REDUCE": r["repeated_reduce_manager_count"],
                "活动状态": r["activity_state"],
            }
            for r in rows
        ],
        width='stretch',
    )


run()
