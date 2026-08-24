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
    st.subheader("个股")
    conn = db.db_conn()
    ticker = st.text_input("输入 Ticker（如 AAPL）").strip().upper()
    if not ticker:
        st.info("请输入 Ticker 查询。")
        conn.close()
        return

    security_id = db.stock_lookup(conn, ticker)
    if security_id is None:
        st.warning(
            f"`{ticker}` 未映射或未解析。当前系统对未经验证的 CUSIP→ticker 映射"
            "一律标记为 UNRESOLVED，不做猜测。"
        )
        conn.close()
        return

    period = db.latest_period(conn)
    holders = db.stock_holders(conn, security_id, period or "")
    st.markdown(f"#### {ticker} · 最新季度 {period or 'N/A'}")
    st.metric("跟踪机构数", len(holders))
    if holders:
        st.dataframe(
            [
                {
                    "机构": h[0],
                    "评分状态": h[1],
                    "变化类型": h[2],
                    "份额变化%": f"{h[3]:+.1%}" if h[3] is not None else None,
                    "组合权重": f"{h[4]:.4%}" if h[4] is not None else None,
                    "权重变化": f"{h[5]:+.4%}" if h[5] is not None else None,
                }
                for h in holders
            ],
            width='stretch',
        )
    else:
        st.info("INSUFFICIENT_DATA：该季度无跟踪机构。")

    st.divider()
    st.markdown("#### 加权共识（治理层）")
    consensus = db.stock_consensus(conn, security_id)
    if consensus:
        st.dataframe(
            [
                {
                    "报告季度": c[0],
                    "共识分": c[1],
                    "参与机构": c[2],
                    "独立策略数": c[3],
                }
                for c in consensus
            ],
            width='stretch',
        )
    else:
        st.info(
            "INSUFFICIENT_DATA：治理层尚未批准任何机构，共识无法计算"
            "（不会用未批准机构生成伪共识）。"
        )

    st.divider()
    st.markdown("#### 趋势")
    trends = db.stock_trends(conn, security_id)
    if trends:
        for h, label, score, p in trends:
            st.write(f"{h}: {label} ({score if score is not None else 'N/A'})")
    else:
        st.info("INSUFFICIENT_HISTORY：无治理层趋势数据。")
    conn.close()


run()


