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
    st.subheader("证券 - 哪些机构报告了该证券的变化")
    store = get_store()
    query = st.text_input("输入 Ticker / CUSIP / 机构名（发行方）查询").strip().upper()
    if not query:
        st.info("请输入查询。支持：已验证 Ticker、CUSIP、发行方名称。多结果会全部列出，不会自动取第一个。")
        return

    matches = store.security_search(query)
    if not matches:
        st.warning("INSUFFICIENT_DATA / UNRESOLVED：未找到匹配证券。系统不做任何猜测映射。")
        return
    st.write(f"匹配 {len(matches)} 个证券（{'多结果，请选择' if len(matches) > 1 else ''}）：")
    labels = {f"{m['ticker'] or m['cusip']} ({m['cusip']})": m["cusip"] for m in matches}
    choice = st.selectbox("选择证券", list(labels))
    ev = store.security_evidence(labels[choice])
    if ev is None:
        st.info("INSUFFICIENT_DATA。")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CUSIP", ev.cusip)
    c2.metric("Ticker", ev.ticker or "未验证")
    c3.metric("解析状态", ev.resolution_status)
    c4.metric("经济类型", ev.economic_type or "未知")
    st.write(f"- 发行方：{ev.issuer or 'N/A'} | 语义分类状态：{ev.classification_status or 'N/A'}")

    st.divider()
    st.markdown("#### 数据新鲜度")
    st.write(f"- 最新报告季度：{ev.latest_report_period or 'N/A'} | "
             f"最新 filing 日期：{ev.latest_filing_date or 'N/A'} | "
             f"距今：{ev.days_since_filing if ev.days_since_filing is not None else 'N/A'} 天")
    st.caption("报告季度 ≠ 实时持仓；13F 存在最长 45 天披露延迟。")

    st.divider()
    st.markdown("#### 最新报告季度机构持有与变化")
    st.write(f"机构实体数：{ev.holder_entity_count} | 已验证独立机构数：{ev.verified_independent_manager_count} | "
             f"活动状态：{ev.activity_state}")
    if ev.holders:
        st.dataframe(
            [
                {
                    "机构": h["manager"],
                    "独立验证": "是" if h["independent"] else "否",
                    "变化类型": h["change_type"],
                    "份额(前/后)": f"{h['shares_prev']} / {h['shares_now']}",
                    "份额变化%": h["share_change_pct"],
                    "权重(前/后)": f"{h['weight_prev']} / {h['weight_now']}",
                    "权重变化": h["weight_change"],
                }
                for h in ev.holders
            ],
            width='stretch',
        )
    else:
        st.info("该季度无跟踪机构持有（可能数据缺失或陈旧）。")

    st.divider()
    st.markdown("#### 活动计数（对称展示）")
    ac = ev.activity_counts
    cols = st.columns(5)
    for col, key in zip(cols, ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")):
        col.metric(key, ac[key])
    st.write(f"- 独立机构增持计数（≥2Q ADD）：{ev.repeated_add_manager_count}")
    st.write(f"- 独立机构减持计数（≥2Q REDUCE）：{ev.repeated_reduce_manager_count}")
    st.caption("增持与减持/退出同权重展示；缺失一侧显示 0。")

    st.divider()
    st.markdown("#### 历史时间线（按报告季度）")
    if ev.timeline:
        st.dataframe(
            [{"报告季度": t["report_period"], "持有机构": t["holders"], "增持": t["adds"], "减持": t["reduces"]}
             for t in ev.timeline if t["holders"] or t["adds"] or t["reduces"]],
            width='stretch',
        )

    st.divider()
    st.markdown("#### 质量")
    st.write(f"- 解析状态：{ev.quality['resolution_status']}")
    st.write(f"- 经济类型：{ev.quality['economic_type'] or '未知'}；分类状态：{ev.quality['classification_status'] or '未知'}")


run()
