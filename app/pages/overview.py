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
    st.subheader("总览 - 我看到的是一份什么数据？")
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
    latest_filing = store.latest_filing_info()
    update = store.update_status()

    st.markdown("#### 数据状态（DATA STATUS）")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最新报告季度", period)
    c2.metric("最新有效 filing 日期", latest_filing["filing_date"] if latest_filing else "N/A")
    c3.metric("机构数量", total)
    c4.metric("本周期已更新", f"{updated}/{total}")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("陈旧机构", len(stale))
    c6.metric("修订 filing", amended)
    c7.metric("已解析证券覆盖", f"{verified}/{sum(res.values())} ({verified/total_res:.1%})")
    c8.metric("本地数据更新", (update or {}).get("last_update_finished_at", "从未记录"))
    if latest_filing:
        st.caption(f"最近一条已入库 filing：{latest_filing['accession']} · "
                   f"form={latest_filing['form_type']} · report={latest_filing['report_period']} · "
                   f"filed={latest_filing['filing_date']}")
    if update:
        upd = update
        flag = "成功" if upd.get("success") else "失败"
        st.caption(f"最近一次更新：{flag}（started={upd.get('last_update_started_at')} "
                   f"finished={upd.get('last_update_finished_at')}）；日志：{upd.get('log_path')}")

    with st.expander("关于两个日期的区别（重要）"):
        st.markdown(
            "- **报告季度（REPORT PERIOD）**：机构披露的是哪个季度末的持仓，例如 2026-06-30。\n"
            "- **filing 日期（FILING DATE）**：这份报告实际公开的日期，例如 2026-08-14。\n"
            "- 也就是说，2026-06-30 不等于“机构在 2026-06-30 当天知道这些持仓”。\n"
            "- 13F 允许最长 45 天延迟，所以看板上的信息总是有延迟的，不是实时仓位。"
        )

    with st.expander("如何使用本看板（快速开始）"):
        st.markdown(
            "- **想看某家机构（例如 Berkshire）最近的变化** → 点左侧「机构」页。\n"
            "- **想看某只股票（例如 GOOGL）被谁增持/减持** → 点左侧「证券」页。\n"
            "- **想看自己的持仓缺少哪些事实** → 点左侧「我的组合」页。\n"
            "- **想看看最近大家 NEW/ADD/REDUCE/EXIT 的排行（中性事实）** → 点左侧「活动探索」页。"
        )

    st.divider()
    st.markdown("#### 本周期发生了什么（What Changed）")
    cols = st.columns(5)
    for col, key in zip(cols, ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")):
        col.metric(key, events[key])
    st.caption("事件计数 = 全部已跟踪机构在最新报告季度的 position_change 数量（事实计数，不是推荐）。")
    st.markdown("按证券维度查看：请前往「活动探索」页（仅描述性排序）。")

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


run()
