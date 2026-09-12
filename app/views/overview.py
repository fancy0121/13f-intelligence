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
from ui import B, T, display_code, display_manager_name


def run() -> None:
    st.subheader(T("总览 - 我看到的是一份什么数据？", "Overview - What data am I looking at?"))
    store = get_store()
    period = store.latest_period()
    if not period:
        st.info(T("INSUFFICIENT_DATA：暂无 filing 数据。", "INSUFFICIENT_DATA: no filing data yet."))
        return

    updated, total = store.manager_update_counts(period)
    stale = store.stale_manager_ids(period)
    amended = store.amendment_count(period)
    res = store.resolution_summary()
    verified = sum(v for k, v in res.items() if k in (
        "VERIFIED_EXACT", "VERIFIED_MULTI_SOURCE", "VERIFIED_HISTORICAL"))
    total_res = sum(res.values())
    q = store.quality_events()
    events = store.event_counts(period)
    latest_filing = store.latest_filing_info()
    update = store.update_status()

    st.markdown(f"#### {T('数据状态', 'DATA STATUS')}")
    c1, c2 = st.columns(2)
    c1.metric(T("最新报告季度", "Latest Quarter"), period)
    c2.metric(T("最新有效 filing 日期", "Latest Filing Date"),
              latest_filing["filing_date"] if latest_filing else "N/A")
    c3, c4 = st.columns(2)
    c3.metric(T("机构数量", "Managers"), total)
    c4.metric(T("本周期已更新", "Updated"), f"{updated}/{total}")
    c5, c6 = st.columns(2)
    c5.metric(T("陈旧机构", "Stale Managers"), len(stale))
    c6.metric(T("修订 filing", "Amendments"), amended)
    c7, c8 = st.columns(2)
    c7.metric(
        T("映射表已解析比例", "Mapping-table Resolution"),
        f"{verified/total_res:.1%}" if total_res else "INSUFFICIENT_DATA",
        delta=f"{verified}/{sum(res.values())}",
        delta_color="off",
    )
    updated_at = (update or {}).get("last_update_finished_at")
    updated_date = str(updated_at).split("T", 1)[0] if updated_at else T("从未记录", "never recorded")
    c8.metric(T("本地数据更新", "Local Data Updated"), updated_date)
    if latest_filing:
        st.caption(
            T(
                f"最近一条已入库 filing：{latest_filing['accession']} · "
                f"form={latest_filing['form_type']} · report={latest_filing['report_period']} · "
                f"filed={latest_filing['filing_date']}",
                f"Latest ingested filing: {latest_filing['accession']} · "
                f"form={latest_filing['form_type']} · report={latest_filing['report_period']} · "
                f"filed={latest_filing['filing_date']}",
            )
        )
    if update:
        upd = update
        flag = T("成功", "OK") if upd.get("success") else T("失败", "FAILED")
        st.caption(
            f"{T('最近一次数据流程', 'Last data run')}: {flag} · "
            f"{T('完成时间', 'Finished')}: "
            f"{str(upd.get('last_update_finished_at') or 'N/A').replace('T', ' ', 1)}"
        )

    with st.expander(T("关于两个日期的区别（重要）", "Two dates - why it matters")):
        st.markdown(
            "**" + T("报告季度", "REPORT PERIOD") + "**：" +
            T("机构披露的是哪个季度末的持仓，例如 2026-06-30。",
              "The quarter-end as of which holdings are reported, e.g. 2026-06-30.") + "\n\n"
            "**" + T("filing 日期", "FILING DATE") + "**：" +
            T("这份报告实际公开的日期，例如 2026-08-14。",
              "The date the report was actually made public, e.g. 2026-08-14.") + "\n\n"
            "- " + T("也就是说，公众不能在 2026-06-30 当天据此得知这些持仓；应以 filing 实际公开时间为准。",
                     "So the public could not know these holdings on 2026-06-30; use the filing's actual public date.") + "\n"
            "- " + T("13F 通常在季末后 45 天内提交；修订与保密处理可能更晚，绝非实时仓位。",
                     "13F is normally filed within 45 days after quarter-end; amendments and confidential treatment may delay it further. Never real-time.")
        )

    with st.expander(T("如何使用本看板（快速开始）", "How to use this dashboard")):
        st.markdown(
            "- **" + T("想看某家机构（例如 Berkshire）最近的变化",
                       "See a manager's (e.g. Berkshire) recent changes") +
            "** → " + T("点左侧「机构」页。", "Open the Managers page.") + "\n"
            "- **" + T("想看某只股票（例如 GOOGL）被谁增持/减持",
                       "See who added/reduced a stock (e.g. GOOGL)") +
            "** → " + T("点左侧「证券」页。", "Open the Securities page.") + "\n"
            "- **" + T("想看自己的持仓缺少哪些事实",
                       "See what facts are missing for your own holdings") +
            "** → " + T("点左侧「我的组合」页。", "Open the My Portfolio page.") + "\n"
            "- **" + T("想看看最近大家 NEW/ADD/REDUCE/EXIT 的排行（中性事实）",
                       "Browse recent NEW/ADD/REDUCE/EXIT rankings") +
            "** → " + T("点左侧「活动探索」页。", "Open the Activity page.")
        )

    st.divider()
    st.markdown(f"#### {T('本周期发生了什么', 'What Changed')}")
    cols = st.columns(5)
    for col, key in zip(cols, ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")):
        col.metric(display_code(key), events[key])
    st.caption(
        B(
            "事件计数 = 全部已跟踪机构在最新报告季度的 position_change 数量（事实计数，不是推荐）",
            "Event counts are position_change totals across tracked managers for the latest "
            "quarter (factual counts, not recommendations)",
        )
    )
    chart_data = pd.DataFrame(
        {T("事件数", "Event count"): [events[k] for k in ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")]},
        index=[display_code(k) for k in ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")],
    )
    st.bar_chart(chart_data)
    st.markdown(T("按证券维度查看：请前往「活动探索」页（仅描述性排序）。",
                  "Per-security view: open the Activity page (descriptive ranking only)."))

    st.divider()
    st.markdown(f"#### {T('数据质量状态', 'Data Quality Status')}")
    quarantined = store.quarantined_periods()
    if quarantined:
        st.dataframe([
            {T("机构", "Manager"): display_manager_name(row["manager"]),
             T("报告季度", "Quarter"): row["report_period"],
             T("隔离申报", "Quarantined accessions"): row["accessions"],
             T("状态", "Status"): T("源数据已隔离", "SOURCE_QUARANTINED")}
            for row in quarantined
        ], hide_index=True, width="stretch")
    if not q:
        st.success(T("未发现数据质量事件。", "No data quality events found."))
    else:
        for event_type, severity, cnt in q:
            label = "⚠️" if severity == "WARN" else "❌"
            st.write(f"{label} {display_code(event_type)}: {cnt}")
    st.write(
        f"- {T('未解析证券', 'Unresolved')}: {res.get('UNRESOLVED', 0)}；"
        f"{T('歧义', 'Ambiguous')}: {res.get('AMBIGUOUS', 0)}；"
        f"{T('冲突', 'Conflict')}: {res.get('CONFLICT', 0)}"
    )
    st.caption(
        B(
            "提示：13F 披露为延迟数据（报告季度 ≠ 实时持仓）。本页不包含任何选股推荐",
            "13F data is delayed (report quarter ≠ real-time holdings); this page contains no stock picks",
        )
    )


run()
