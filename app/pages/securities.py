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


def run() -> None:
    st.subheader(T("证券 - 哪些机构报告了该证券的变化",
                   "Securities - Which managers reported changes to this security?"))
    with st.expander(T("如何使用本页", "How to use this page")):
        st.markdown(
            "1. " + T("输入 Ticker（如 GOOGL）、CUSIP（如 02079K305）或发行方名称（如 Alphabet）。",
                      "Enter a Ticker (e.g. GOOGL), CUSIP (e.g. 02079K305) or issuer name (e.g. Alphabet).") + "\n"
            "2. " + T("如果找到多个候选，系统会全部列出，请你选择正确的证券。",
                      "If multiple candidates are found, they are all listed for you to choose.") + "\n"
            "3. " + T("页面会显示：身份信息、数据新旧、当前持有机构及各自动作、增持/减持/退出计数、"
                      "连续两个季度同向的机构数、以及历史时间线。",
                      "The page shows identity, data freshness, current holders and their actions, "
                      "add/reduce/exit counts, consecutive-quarter counts, and a history timeline.") + "\n"
            "4. " + T("注意：这里展示的是「已披露事实」，不是推荐。",
                      "Note: this shows disclosed facts, not recommendations.")
        )
    store = get_store()
    query = st.text_input(
        T("输入 Ticker / CUSIP / 发行方名称查询", "Search Ticker / CUSIP / Issuer name"),
        placeholder=T("例如 GOOGL 或 02079K305 或 Alphabet…", "e.g. GOOGL, 02079K305, Alphabet…"),
    ).strip().upper()
    if not query:
        st.info(
            T(
                "请输入查询。支持：已验证 Ticker、CUSIP、发行方名称。多结果会全部列出，不会自动取第一个。",
                "Enter a query. Supported: verified Ticker, CUSIP, issuer name. "
                "Multiple results are all listed - nothing is auto-picked.",
            )
        )
        return

    matches = store.security_search(query)
    if not matches:
        st.warning(
            T(
                "INSUFFICIENT_DATA / UNRESOLVED：未找到匹配证券。系统不做任何猜测映射。",
                "INSUFFICIENT_DATA / UNRESOLVED: no matching security. The system never guesses mappings.",
            )
        )
        return
    st.write(
        T(
            f"匹配 {len(matches)} 个证券" + ("（多结果，请选择）" if len(matches) > 1 else ""),
            f"{len(matches)} security match(es)" + (" (multiple - please select)" if len(matches) > 1 else ""),
        )
    )
    labels = {f"{m['ticker'] or m['cusip']} ({m['cusip']})": m["cusip"] for m in matches}
    choice = searchable_select(
        T("选择证券", "Select Security"),
        list(labels),
        key="security_pick",
        help_text=T("输入关键字筛选候选，点击按钮选择", "Type to filter candidates, click to select"),
    )
    if choice is None:
        st.info(T("请选择一个证券。", "Please select a security."))
        return
    ev = store.security_evidence(labels[choice])
    if ev is None:
        st.info(T("INSUFFICIENT_DATA。", "INSUFFICIENT_DATA."))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CUSIP", ev.cusip)
    c2.metric("Ticker", ev.ticker or T("未验证", "unverified"))
    c3.metric(T("解析状态", "Resolution"), ev.resolution_status)
    c4.metric(T("经济类型", "Economic Type"), ev.economic_type or T("未知", "unknown"))
    st.write(
        f"- {T('发行方', 'Issuer')}：{ev.issuer or 'N/A'} | "
        f"{T('语义分类状态', 'Classification')}：{ev.classification_status or 'N/A'}"
    )

    st.divider()
    st.markdown(f"#### {T('数据新鲜度', 'Data Freshness')}")
    st.write(
        f"- {T('最新报告季度', 'Latest Quarter')}：{ev.latest_report_period or 'N/A'} | "
        f"{T('最新 filing 日期', 'Latest Filing Date')}：{ev.latest_filing_date or 'N/A'} | "
        f"{T('距今', 'Days ago')}：{ev.days_since_filing if ev.days_since_filing is not None else 'N/A'} "
        f"{T('天', 'days')}"
    )
    st.caption(
        T("报告季度 ≠ 实时持仓；13F 存在最长 45 天披露延迟。",
          "Report quarter ≠ real-time holdings; 13F has up to 45 days of disclosure lag.")
    )

    st.divider()
    st.markdown(f"#### {T('最新报告季度机构持有与变化', 'Latest-quarter holders and changes')}")
    st.write(
        f"{T('机构实体数', 'Entities')}：{ev.holder_entity_count} | "
        f"{T('已验证独立机构数', 'Verified independent')}：{ev.verified_independent_manager_count} | "
        f"{T('活动状态', 'Activity')}：{ev.activity_state}"
    )
    if ev.holders:
        st.dataframe(
            [
                {
                    T("机构", "Manager"): h["manager"],
                    T("独立验证", "Independent"): T("是", "Yes") if h["independent"] else T("否", "No"),
                    T("变化类型", "Change"): h["change_type"],
                    T("份额(前/后)", "Shares (prev/now)"): f"{h['shares_prev']} / {h['shares_now']}",
                    T("份额变化%", "Shares %"): h["share_change_pct"],
                    T("权重(前/后)", "Weight (prev/now)"): f"{h['weight_prev']} / {h['weight_now']}",
                    T("权重变化", "Weight Δ"): h["weight_change"],
                }
                for h in ev.holders
            ],
            width='stretch',
        )
    else:
        st.info(T("该季度无跟踪机构持有（可能数据缺失或陈旧）。",
                  "No tracked manager held this security in the latest quarter "
                  "(data may be missing or stale)."))

    st.divider()
    st.markdown(f"#### {T('活动计数（对称展示）', 'Activity counts (symmetric)')}")
    ac = ev.activity_counts
    cols = st.columns(5)
    for col, key in zip(cols, ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")):
        col.metric(key, ac[key])
    st.write(
        f"- {T('独立机构增持计数', 'Independent ADD count')}（≥2Q ADD）：{ev.repeated_add_manager_count}\n"
        f"- {T('独立机构减持计数', 'Independent REDUCE count')}（≥2Q REDUCE）：{ev.repeated_reduce_manager_count}"
    )
    st.caption(
        B("增持与减持/退出同权重展示；缺失一侧显示 0",
          "Adds and reduces/exits are shown with equal weight; missing side shows 0")
    )

    st.divider()
    st.markdown(f"#### {T('历史时间线（按报告季度）', 'History timeline (by quarter)')}")
    if ev.timeline:
        st.dataframe(
            [
                {
                    T("报告季度", "Quarter"): t["report_period"],
                    T("持有机构", "Holders"): t["holders"],
                    T("增持", "Adds"): t["adds"],
                    T("减持", "Reduces"): t["reduces"],
                }
                for t in ev.timeline if t["holders"] or t["adds"] or t["reduces"]
            ],
            width='stretch',
        )

    st.divider()
    st.markdown(f"#### {T('质量', 'Quality')}")
    st.write(f"- {T('解析状态', 'Resolution')}：{ev.quality['resolution_status']}")
    st.write(
        f"- {T('经济类型', 'Economic Type')}：{ev.quality['economic_type'] or T('未知', 'unknown')}；"
        f"{T('分类状态', 'Classification')}：{ev.quality['classification_status'] or T('未知', 'unknown')}"
    )


run()
