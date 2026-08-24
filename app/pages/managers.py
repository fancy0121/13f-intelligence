from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import db  # noqa: E402


def run() -> None:
    st.subheader("机构")
    conn = db.db_conn()
    managers = db.managers_list(conn)
    if not managers:
        st.info("暂无机构数据。")
        conn.close()
        return

    names = {m[1]: m[0] for m in managers}
    selected = st.selectbox("选择机构", sorted(names))
    manager_id = names[selected]
    summary = db.manager_summary(conn, manager_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("策略类型", summary.get("strategy_type") or "未分类")
    c2.metric("评分状态", summary.get("scoring_status") or "N/A")
    c3.metric("信号质量", summary.get("signal_quality") if summary.get("signal_quality") is not None else "NULL")
    c4.metric("方法版本", summary.get("methodology_version") or "N/A")
    if summary.get("notes"):
        st.caption(f"Scope / 备注：{summary['notes']}")

    st.divider()
    st.markdown("#### 最新季度动作")
    activity = db.manager_activity(conn, manager_id)
    if activity:
        cols = st.columns(5)
        for col, key in zip(cols, ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")):
            col.metric(key, activity.get(key, 0))
    else:
        st.info("该机构暂无动作数据。")

    st.divider()
    st.markdown("#### 最新季度 Top 持仓")
    period = db.latest_period(conn)
    top = db.manager_top_holdings(conn, manager_id, period or "")
    if top:
        st.dataframe(
            [
                {
                    "Ticker": t or c,
                    "CUSIP": c,
                    "Issuer": i,
                    "Shares": s,
                    "Value": v,
                    "Weight": f"{w:.4%}" if w is not None else None,
                    "Put/Call": pc or "股票",
                }
                for t, c, i, s, v, w, pc in top
            ],
            width='stretch',
        )
    else:
        st.info("暂无持仓数据。")

    st.divider()
    st.markdown("#### 季度历史")
    history = db.manager_history(conn, manager_id)
    if history:
        st.dataframe(
            [{"报告季度": p, "filing 数": n} for p, n in history],
            width='stretch',
        )
    conn.close()


run()


