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
from ui import B, T, searchable_select


def _fmt(x, pct=False, default="N/A"):
    if x is None:
        return default
    return f"{x:.4%}" if pct else f"{x:,.0f}"


def run() -> None:
    st.subheader(T("机构 - 该机构最近披露了什么变化",
                   "Managers - What did this manager disclose recently?"))
    with st.expander(T("如何使用本页", "How to use this page")):
        st.markdown(
            "1. " + T("在搜索框输入机构名称关键字（例如 Berkshire），然后点击下方出现的机构按钮。",
                      "Type a manager keyword (e.g. Berkshire) in the search box, then click the manager button.") + "\n"
            "2. " + T("顶部显示这份披露的时间信息（报告季度、filing 日期、距今几天、是否修订）。",
                      "The top shows filing time info (report quarter, filing date, days ago, amended).") + "\n"
            "3. " + T("「最新报告季度变化」分 NEW / ADD / REDUCE / EXIT 四张表，列出该机构增减持的证券。",
                      "Latest-quarter changes are split into NEW / ADD / REDUCE / EXIT tables.") + "\n"
            "4. " + T("「Top 持仓」按报告价值列出最大持仓；「重复报告活动」显示连续至少两个季度同向的证券。",
                      "Top Holdings lists largest positions by reported value; Repeated Activity shows "
                      "securities with the same direction for at least two consecutive quarters.")
        )
    store = get_store()
    managers = store.managers_list()
    if not managers:
        st.info(T("INSUFFICIENT_DATA：暂无机构数据。", "INSUFFICIENT_DATA: no manager data yet."))
        return
    id_by_name = {m["name"]: m["manager_id"] for m in managers}
    names = sorted(id_by_name)
    selected = searchable_select(
        T("选择机构", "Select Manager"),
        names,
        key="manager_pick",
        help_text=T("输入关键字筛选机构，点击按钮选择", "Type to filter managers, click a button to select"),
    )
    if selected is None:
        st.info(T("请先选择一家机构。", "Please select a manager first."))
        return
    ev = store.manager_evidence(id_by_name[selected])
    if ev is None:
        st.info(T("INSUFFICIENT_DATA。", "INSUFFICIENT_DATA."))
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(T("报告季度", "Quarter"), ev.latest_report_period or "N/A")
    c2.metric(T("filing 日期", "Filing Date"), ev.latest_filing_date or "N/A")
    c3.metric(T("距今天数", "Days Ago"),
              ev.days_since_filing if ev.days_since_filing is not None else "N/A")
    c4.metric(T("陈旧", "Stale"), T("是", "Yes") if ev.stale else T("否", "No"))
    c5.metric(T("修订", "Amended"), T("是", "Yes") if ev.amended else T("否", "No"))
    st.caption(
        T(
            f"验证状态：{ev.validation_status} | 持仓数：{ev.position_count} | "
            f"报告总值：{ev.total_value if ev.total_value is not None else 'N/A'}",
            f"Validation: {ev.validation_status} | Positions: {ev.position_count} | "
            f"Total value: {ev.total_value if ev.total_value is not None else 'N/A'}",
        )
    )

    st.divider()
    st.markdown(f"#### {T('最新报告季度变化', 'Latest Quarter Changes')} (NEW / ADD / REDUCE / EXIT)")
    if any(ev.latest_changes.values()):
        for ct in ("NEW", "ADD", "REDUCE", "EXIT"):
            rows = ev.latest_changes.get(ct, [])
            st.markdown(f"**{ct}** ({len(rows)})")
            if rows:
                st.dataframe(
                    [
                        {
                            "CUSIP": r["cusip"],
                            T("发行方", "Issuer"): r["issuer"],
                            T("份额变化", "Shares Change"):
                                r["shares_now"] if r["shares_prev"] is None
                                else (r["shares_now"] - (r["shares_prev"] or 0)),
                            T("权重(前/后)", "Weight (prev/now)"):
                                f"{r['weight_prev']} / {r['weight_now']}",
                            T("解析状态", "Resolution"): r["resolution_status"],
                        }
                        for r in rows[:50]
                    ],
                    width='stretch',
                )
    else:
        st.info(T("该机构最新报告季度无变化数据。",
                  "No change data for this manager's latest quarter."))

    st.divider()
    st.markdown(f"#### {T('Top 持仓（按报告价值）', 'Top Holdings (by reported value)')}")
    if ev.top_holdings:
        st.dataframe(
            [
                {
                    "Ticker": r["ticker"] or r["cusip"],
                    "CUSIP": r["cusip"],
                    T("发行方", "Issuer"): r["issuer"],
                    T("份额", "Shares"): _fmt(r["shares"]),
                    T("价值", "Value"): _fmt(r["value"]),
                    T("权重", "Weight"): _fmt(r["weight"], pct=True),
                    T("类别", "Put/Call"): r["put_call"] or T("股票", "Equity"),
                    T("解析状态", "Resolution"): r["resolution_status"],
                }
                for r in ev.top_holdings
            ],
            width='stretch',
        )

    st.divider()
    st.markdown(
        f"#### {T('重复报告活动（连续 ≥2 个报告季度，缺失季度会中断）', 'Repeated Activity (≥2 consecutive quarters)')}"
    )
    st.write(
        f"- {T('重复增持', 'Repeated ADD')}（≥2Q ADD）："
        f"{ev.repeated.get('repeated_add_manager_count', 0)} {T('个证券', 'securities')}"
    )
    st.write(
        f"- {T('重复减持', 'Repeated REDUCE')}（≥2Q REDUCE）："
        f"{ev.repeated.get('repeated_reduce_manager_count', 0)} {T('个证券', 'securities')}"
    )

    st.divider()
    st.markdown(f"#### {T('数据质量', 'Data Quality')}")
    st.write(f"- {T('Top10 持仓中未解析/冲突', 'Unresolved/conflict in top 10')}："
             f"{ev.quality['unresolved_or_conflict_top10']}")
    st.write(f"- {T('缺失报告季度数', 'Missing quarters')}：{ev.quality['missing_periods']}")
    st.write(f"- {T('修订', 'Amended')}：{ev.quality['amended']}；"
             f"{T('陈旧', 'Stale')}：{ev.quality['stale']}")
    st.caption(
        B(
            "注：重复活动是已披露行为的描述性事实，不代表预测性意义（见方法论页）",
            "Repeated activity is a descriptive fact of disclosed behavior, not forward-looking "
            "(see the Methodology page)",
        )
    )


run()
