from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from store import get_store
from thirteenf.product.evidence import load_portfolio_rows, save_portfolio_rows
from ui import B, T, searchable_select


def _portfolio_path() -> Path:
    session = st.session_state.get("portfolio_path")
    if session:
        return Path(session)
    env = os.environ.get("THIRTEENF_PORTFOLIO")
    if env:
        return Path(env)
    return ROOT / "config" / "portfolio.csv"


def run() -> None:
    st.subheader(T("我的组合 - 持仓事实交叉验证",
                   "My Portfolio - Factual cross-check for your holdings"))
    st.caption(
        B(
            "本页只展示与你持仓相关的已披露事实（含增持、减持、退出、陈旧、质量），不做任何买卖建议，"
            "也不推断你的投资论点。你可以直接在页面里添加/删除你的持仓，不需要编辑任何文件",
            "This page shows disclosed facts relevant to your holdings (adds, reduces, exits, staleness, "
            "quality) only - no trade recommendations, no inference about your thesis. Add/remove holdings here; "
            "no file editing needed",
        )
    )
    store = get_store()
    portfolio_path = _portfolio_path()
    rows = load_portfolio_rows(portfolio_path)

    st.divider()
    st.markdown(f"#### {T('我的持仓（可直接编辑）', 'My Holdings (editable)')}")
    st.caption(
        T("添加时系统会先搜索并列出候选；如果名称有歧义，你必须明确选择，系统不会自动替你选。",
          "The system searches and lists candidates; if ambiguous you must choose explicitly - "
          "nothing is auto-picked.")
    )
    with st.form("portfolio_add"):
        c = st.columns([3, 1])
        ticker = c[0].text_input(
            T("输入 Ticker / CUSIP / 发行方名称", "Enter Ticker / CUSIP / Issuer name"),
            placeholder=T("例如 GOOGL…", "e.g. GOOGL…"),
        ).strip().upper()
        weight = c[1].text_input(
            T("权重（可选）", "Weight (optional)"),
            placeholder=T("如 0.05", "e.g. 0.05"),
        ).strip()
        add_submitted = st.form_submit_button(T("查找并添加", "Find & Add"))
    if add_submitted and ticker:
        matches = store.security_search(ticker)
        if len(matches) == 1:
            m = matches[0]
            rows = [r for r in rows if r["ticker"] != (m["ticker"] or m["cusip"])]
            rows.append({"ticker": m["ticker"] or m["cusip"], "weight": weight})
            save_portfolio_rows(portfolio_path, rows)
            st.success(T(f"已添加 {m['ticker'] or m['cusip']}（{m['cusip']}）。",
                         f"Added {m['ticker'] or m['cusip']} ({m['cusip']})."))
            st.rerun()
        elif len(matches) > 1:
            st.warning(T("找到多个候选，请选择正确的证券：", "Multiple candidates - please choose:"))
            labels = {f"{m['ticker'] or m['cusip']} ({m['cusip']})": m for m in matches}
            choice = searchable_select(
                T("候选", "Candidates"),
                list(labels),
                key="portfolio_pick",
                help_text=T("输入关键字筛选候选，点击按钮选择", "Type to filter candidates, click to select"),
            )
            if choice is not None and st.button(T("添加所选", "Add selected")):
                m = labels[choice]
                rows = [r for r in rows if r["ticker"] != (m["ticker"] or m["cusip"])]
                rows.append({"ticker": m["ticker"] or m["cusip"], "weight": weight})
                save_portfolio_rows(portfolio_path, rows)
                st.success(T(f"已添加 {m['ticker'] or m['cusip']}（{m['cusip']}）。",
                             f"Added {m['ticker'] or m['cusip']} ({m['cusip']})."))
                st.rerun()
        else:
            st.warning(
                T("未找到匹配证券（可能是未解析身份）。系统不会猜测映射。",
                  "No matching security (possibly unresolved identity). No guessed mappings.")
            )

    if rows:
        st.markdown(f"##### {T('当前持仓（勾选后点保存可删除）', 'Current holdings (check to remove, then save)')}")
        with st.form("portfolio_remove"):
            keep = []
            for r in rows:
                if not st.checkbox(
                    T(f"删除：{r['ticker']}（权重 {r['weight'] or '未填'}）",
                      f"Remove: {r['ticker']} (weight {r['weight'] or 'not set'})"),
                    key=f"del_{r['ticker']}_{r['weight']}",
                ):
                    keep.append(r)
            if st.form_submit_button(T("保存修改", "Save changes")):
                save_portfolio_rows(portfolio_path, keep)
                st.success(T("已保存。", "Saved."))
                st.rerun()

    st.divider()
    st.markdown(f"#### {T('持仓事实交叉验证（对称展示）', 'Factual cross-check (symmetric)')}")
    out = store.portfolio_evidence(portfolio_path)
    if out == "SETUP_REQUIRED":
        st.warning(
            T("SETUP_REQUIRED：你的持仓列表为空。请在上方添加你的第一只股票。系统不会生成演示组合。",
              "SETUP_REQUIRED: your holdings list is empty. Add your first stock above. "
              "No demo portfolio is generated.")
        )
    else:
        st.dataframe(
            [
                {
                    "Ticker": r["ticker"],
                    T("权重", "Weight"): r["weight"],
                    T("状态", "Status"): r["status"],
                    T("持有机构实体数", "Entities"): r["holder_entity_count"],
                    T("独立增持", "Ind. ADD"): r["independent_add_manager_count"],
                    T("独立减持", "Ind. REDUCE"): r["independent_reduce_manager_count"],
                    T("独立退出", "Ind. EXIT"): r["independent_exit_manager_count"],
                    T("独立新增", "Ind. NEW"): r["independent_new_manager_count"],
                    T("重复增持", "Repeated ADD"): r["repeated_add_manager_count"],
                    T("重复减持", "Repeated REDUCE"): r["repeated_reduce_manager_count"],
                    T("活动状态", "Activity"): r["activity_state"],
                    T("数据距今(天)", "Days since filing"): r["days_since_filing"],
                    T("解析状态", "Resolution"): r["resolution_status"],
                }
                for r in out
            ],
            width='stretch',
        )
        st.caption(
            B("对称规则：增持/减持/退出同权重展示；缺失一侧显示 0；不突出任何单一方向",
              "Symmetric: adds/reduces/exits shown with equal weight; missing side shows 0; "
              "no single direction is highlighted")
        )

    with st.expander(T("如何使用本页", "How to use this page")):
        st.markdown(
            "1. " + T("在「我的持仓」输入框输入你要跟踪的股票（Ticker 或名称）。",
                      "Enter a stock you track in the My Holdings box (Ticker or name).") + "\n"
            "2. " + T("系统会先搜索；如果结果有歧义，请从候选里选择正确的那个。",
                      "The system searches first; if ambiguous, pick the correct candidate.") + "\n"
            "3. " + T("添加后页面会立即显示该股票的事实（谁增持、谁减持、谁退出、数据新旧、身份质量）。",
                      "After adding, the page shows that stock's facts (who added/reduced/exited, "
                      "freshness, identity quality).") + "\n"
            "4. " + T("删除时勾选对应行并点「保存修改」。",
                      "To remove, check the row and click Save changes.") + "\n"
            "5. " + T("你的持仓保存在本地 `config/portfolio.csv`，下次打开看板会自动载入。",
                      "Your holdings are stored in `config/portfolio.csv` and reload automatically.")
        )


run()
