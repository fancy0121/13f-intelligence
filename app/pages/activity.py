from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from store import get_store
from ui import B, T, searchable_select


METRICS = {
    T("独立机构新增计数", "Independent NEW"): "independent_new_manager_count",
    T("独立机构增持计数", "Independent ADD"): "independent_add_manager_count",
    T("独立机构减持计数", "Independent REDUCE"): "independent_reduce_manager_count",
    T("独立机构退出计数", "Independent EXIT"): "independent_exit_manager_count",
    T("重复增持计数", "Repeated ADD (≥2Q)"): "repeated_add_manager_count",
    T("重复减持计数", "Repeated REDUCE (≥2Q)"): "repeated_reduce_manager_count",
    T("持有机构实体数", "Holder entities"): "holder_entity_count",
}


def run() -> None:
    st.subheader(T("活动探索 - 描述性排序（非推荐榜）",
                   "Activity - Descriptive ranking (not a recommendation list)"))
    with st.expander(T("如何使用本页", "How to use this page")):
        st.markdown(
            "1. " + T("输入关键字筛选排序指标，然后点击指标按钮（例如「独立机构增持计数」）。",
                      "Type to filter the ranking metric, then click it (e.g. Independent ADD).") + "\n"
            "2. " + T("列表按该指标从高到低展示证券，并同时显示计数、解析状态、活动状态。",
                      "Securities are ranked by that metric, showing counts, resolution and activity.") + "\n"
            "3. " + T("这是中性事实排序：数字是「多少家已验证独立机构报告了该动作」，不是建议你买或卖。",
                      "This is a neutral factual ranking: the number of verified independent managers "
                      "reporting the action - not a trading suggestion.")
        )
    store = get_store()
    metric_label = searchable_select(
        T("排序指标", "Ranking Metric"),
        list(METRICS),
        key="metric_pick",
        help_text=T("输入关键字筛选，点击按钮选择", "Type to filter, click to select"),
    )
    if metric_label is None:
        st.info(T("请先选择排序指标。", "Please select a ranking metric first."))
        return
    rows = store.activity_explorer(METRICS[metric_label], limit=100)
    st.caption(
        B(
            "说明：计数为最新报告季度内“已验证独立机构”的动作数量；重复计数为连续 ≥2 个报告季度同方向"
            "（缺失季度中断）。身份未验证/未解析证券仍会显示其解析状态，不做隐藏过滤。该页仅为中性事实排序，"
            "不构成任何“最佳/机会”含义。",
            "Counts are actions by verified independent managers in the latest quarter; repeated counts "
            "require ≥2 consecutive quarters (gaps break the streak). Unresolved securities keep their "
            "status visible. Neutral factual ranking only - no 'best' meaning.",
        )
    )
    if not rows:
        st.info(T("INSUFFICIENT_DATA。", "INSUFFICIENT_DATA."))
        return

    # top-10 mini chart (factual counts only)
    chart = pd.DataFrame(
        [
            {
                T("证券", "Security"): r["ticker"] or r["cusip"],
                "count": r[METRICS[metric_label]] or 0,
            }
            for r in rows[:10]
        ]
    )
    if not chart.empty:
        chart = chart.set_index(T("证券", "Security"))
        st.bar_chart(chart)

    st.dataframe(
        [
            {
                "Ticker": r["ticker"] or r["cusip"],
                "CUSIP": r["cusip"],
                T("发行方", "Issuer"): r["issuer"],
                T("解析状态", "Resolution"): r["resolution_status"],
                T("经济类型", "Economic Type"): r["economic_type"],
                T("持有机构实体数", "Entities"): r["holder_entity_count"],
                "独立NEW": r["independent_new_manager_count"],
                "独立ADD": r["independent_add_manager_count"],
                "独立REDUCE": r["independent_reduce_manager_count"],
                "独立EXIT": r["independent_exit_manager_count"],
                "重复ADD": r["repeated_add_manager_count"],
                "重复REDUCE": r["repeated_reduce_manager_count"],
                T("活动状态", "Activity"): r["activity_state"],
            }
            for r in rows
        ],
        width='stretch',
    )


run()
