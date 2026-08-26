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


def _portfolio_path() -> Path:
    session = st.session_state.get("portfolio_path")
    if session:
        return Path(session)
    env = os.environ.get("THIRTEENF_PORTFOLIO")
    if env:
        return Path(env)
    return ROOT / "config" / "portfolio.csv"


def run() -> None:
    st.subheader("我的组合 - 持仓事实交叉验证")
    st.caption("本页只展示与你持仓相关的已披露事实（含增持、减持、退出、陈旧、质量），"
               "不做任何买卖建议，也不推断你的投资论点。你可以直接在页面里添加/删除你的持仓，"
               "不需要编辑任何文件。")
    store = get_store()
    portfolio_path = _portfolio_path()
    rows = load_portfolio_rows(portfolio_path)

    st.divider()
    st.markdown("#### 我的持仓（可直接编辑）")
    st.caption("添加时系统会先搜索并列出候选；如果名称有歧义，你必须明确选择，系统不会自动替你选。")
    with st.form("portfolio_add"):
        c = st.columns([3, 1])
        ticker = c[0].text_input("输入 Ticker / CUSIP / 发行方名称").strip().upper()
        weight = c[1].text_input("权重（可选，如 0.05）").strip()
        add_submitted = st.form_submit_button("查找并添加")
    if add_submitted and ticker:
        matches = store.security_search(ticker)
        if len(matches) == 1:
            m = matches[0]
            rows = [r for r in rows if r["ticker"] != (m["ticker"] or m["cusip"])]
            rows.append({"ticker": m["ticker"] or m["cusip"], "weight": weight})
            save_portfolio_rows(portfolio_path, rows)
            st.success(f"已添加 {m['ticker'] or m['cusip']}（{m['cusip']}）。")
            st.rerun()
        elif len(matches) > 1:
            st.warning("找到多个候选，请选择正确的证券：")
            labels = {f"{m['ticker'] or m['cusip']} ({m['cusip']})": m for m in matches}
            choice = st.selectbox("候选", list(labels))
            if st.button("添加所选"):
                m = labels[choice]
                rows = [r for r in rows if r["ticker"] != (m["ticker"] or m["cusip"])]
                rows.append({"ticker": m["ticker"] or m["cusip"], "weight": weight})
                save_portfolio_rows(portfolio_path, rows)
                st.success(f"已添加 {m['ticker'] or m['cusip']}（{m['cusip']}）。")
                st.rerun()
        else:
            st.warning("未找到匹配证券（可能是未解析身份）。系统不会猜测映射。")

    if rows:
        st.markdown("##### 当前持仓（勾选后点保存可删除）")
        with st.form("portfolio_remove"):
            keep = []
            for r in rows:
                if not st.checkbox(f"删除：{r['ticker']}（权重 {r['weight'] or '未填'}）", key=f"del_{r['ticker']}_{r['weight']}"):
                    keep.append(r)
            if st.form_submit_button("保存修改"):
                save_portfolio_rows(portfolio_path, keep)
                st.success("已保存。")
                st.rerun()

    st.divider()
    st.markdown("#### 持仓事实交叉验证（对称展示）")
    out = store.portfolio_evidence(portfolio_path)
    if out == "SETUP_REQUIRED":
        st.warning("SETUP_REQUIRED：你的持仓列表为空。请在上方添加你的第一只股票。系统不会生成演示组合。")
    else:
        st.dataframe(
            [
                {
                    "Ticker": r["ticker"],
                    "权重": r["weight"],
                    "状态": r["status"],
                    "持有机构实体数": r["holder_entity_count"],
                    "独立增持": r["independent_add_manager_count"],
                    "独立减持": r["independent_reduce_manager_count"],
                    "独立退出": r["independent_exit_manager_count"],
                    "独立新增": r["independent_new_manager_count"],
                    "重复增持(≥2Q)": r["repeated_add_manager_count"],
                    "重复减持(≥2Q)": r["repeated_reduce_manager_count"],
                    "活动状态": r["activity_state"],
                    "数据距今(天)": r["days_since_filing"],
                    "解析状态": r["resolution_status"],
                }
                for r in out
            ],
            width='stretch',
        )
        st.caption("对称规则：增持/减持/退出同权重展示；缺失一侧显示 0；不突出任何单一方向。")

    with st.expander("如何使用本页"):
        st.markdown(
            "1. 在「我的持仓」输入框输入你要跟踪的股票（Ticker 或名称）。\n"
            "2. 系统会先搜索；如果结果有歧义，请从候选里选择正确的那个。\n"
            "3. 添加后页面会立即显示该股票的事实（谁增持、谁减持、谁退出、数据新旧、身份质量）。\n"
            "4. 删除时勾选对应行并点「保存修改」。\n"
            "5. 你的持仓保存在本地 `config/portfolio.csv`，下次打开看板会自动载入。"
        )


run()
