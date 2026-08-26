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
    st.subheader("总览 - 系统与披露状态")
    store = get_store()
    period = store.latest_period()
    if not period:
        st.info("INSUFFICIENT_DATA：暂无 filing 数据。")
        return

    updated, total = store.manager_update_counts(period)
    stale = store.stale_manager_ids(period)
    amended = store.amendment_count(period)
    res = store.resolution_summary()
    verified = sum(v for k, v in res.items() if k in (
        "VERIFIED_EXACT", "VERIFIED_MULTI_SOURCE", "VERIFIED_HISTORICAL"))
    total_res = sum(res.values()) or 1
    q = store.quality_events()
    events = store.event_counts(period)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("最新报告季度", period)
    c2.metric("机构更新覆盖", f"{updated}/{total}")
    c3.metric("陈旧机构", len(stale))
    c4.metric("修订 filing 数", amended)
    c5.metric("已解析证券覆盖", f"{verified}/{sum(res.values())} ({verified/total_res:.1%})")

    st.divider()
    st.markdown("#### 数据质量状态")
    if not q:
        st.success("未发现数据质量事件。")
    else:
        for event_type, severity, cnt in q:
            label = "⚠️" if severity == "WARN" else "❌"
            st.write(f"{label} {event_type}: {cnt}")
    st.write(f"- 未解析证券：{res.get('UNRESOLVED', 0)}；歧义：{res.get('AMBIGUOUS', 0)}；冲突：{res.get('CONFLICT', 0)}")
    st.caption("提示：13F 披露为延迟数据（报告季度 ≠ 实时持仓）。本页不包含任何选股推荐。")

    st.divider()
    st.markdown("#### 最新披露周期事件计数（What Changed）")
    cols = st.columns(5)
    for col, key in zip(cols, ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")):
        col.metric(key, events[key])
    st.caption("事件计数 = 全部已跟踪机构在最新报告季度的 position_change 数量（事实计数，非推荐）。")
    st.markdown("按证券维度查看：请前往「活动探索」页（仅描述性排序）。")


run()
