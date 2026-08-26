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


def _fmt(x, pct=False, default="N/A"):
    if x is None:
        return default
    return f"{x:.4%}" if pct else f"{x:,.0f}"


def run() -> None:
    st.subheader("机构 - 该机构最近披露了什么变化")
    store = get_store()
    managers = store.managers_list()
    if not managers:
        st.info("INSUFFICIENT_DATA：暂无机构数据。")
        return
    names = {m["name"]: m["manager_id"] for m in managers}
    selected = st.selectbox("选择机构", sorted(names))
    ev = store.manager_evidence(names[selected])
    if ev is None:
        st.info("INSUFFICIENT_DATA。")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("报告季度", ev.latest_report_period or "N/A")
    c2.metric("filing 日期", ev.latest_filing_date or "N/A")
    c3.metric("距今天数", ev.days_since_filing if ev.days_since_filing is not None else "N/A")
    c4.metric("陈旧", "是" if ev.stale else "否")
    c5.metric("修订", "是" if ev.amended else "否")
    st.caption(f"验证状态：{ev.validation_status} | 持仓数：{ev.position_count} | "
               f"报告总值：{ev.total_value if ev.total_value is not None else 'N/A'}")

    st.divider()
    st.markdown("#### 最新报告季度变化（NEW / ADD / REDUCE / EXIT）")
    if any(ev.latest_changes.values()):
        for ct in ("NEW", "ADD", "REDUCE", "EXIT"):
            rows = ev.latest_changes.get(ct, [])
            st.markdown(f"**{ct}** ({len(rows)})")
            if rows:
                st.dataframe(
                    [
                        {
                            "CUSIP": r["cusip"],
                            "Issuer": r["issuer"],
                            "份额变化": r["shares_now"] if r["shares_prev"] is None else (r["shares_now"] - (r["shares_prev"] or 0)),
                            "权重(前/后)": f"{r['weight_prev']} / {r['weight_now']}",
                            "解析状态": r["resolution_status"],
                        }
                        for r in rows[:50]
                    ],
                    width='stretch',
                )
    else:
        st.info("该机构最新报告季度无变化数据。")

    st.divider()
    st.markdown("#### Top 持仓（按报告价值）")
    if ev.top_holdings:
        st.dataframe(
            [
                {
                    "Ticker": r["ticker"] or r["cusip"],
                    "CUSIP": r["cusip"],
                    "Issuer": r["issuer"],
                    "Shares": _fmt(r["shares"]),
                    "Value": _fmt(r["value"]),
                    "Weight": _fmt(r["weight"], pct=True),
                    "Put/Call": r["put_call"] or "股票",
                    "解析状态": r["resolution_status"],
                }
                for r in ev.top_holdings
            ],
            width='stretch',
        )

    st.divider()
    st.markdown("#### 重复报告活动（连续 ≥2 个报告季度，缺失季度会中断）")
    st.write(f"- 重复增持（≥2Q ADD）：{ev.repeated.get('repeated_add_manager_count', 0)} 个证券")
    st.write(f"- 重复减持（≥2Q REDUCE）：{ev.repeated.get('repeated_reduce_manager_count', 0)} 个证券")

    st.divider()
    st.markdown("#### 数据质量")
    st.write(f"- Top10 持仓中未解析/冲突：{ev.quality['unresolved_or_conflict_top10']}")
    st.write(f"- 缺失报告季度数：{ev.quality['missing_periods']}")
    st.write(f"- 修订：{ev.quality['amended']}；陈旧：{ev.quality['stale']}")
    st.caption("注：重复活动是已披露行为的描述性事实，不代表预测性意义（见方法论页）。")


run()
