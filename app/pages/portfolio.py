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
from thirteenf.portfolio import cross_check


def run() -> None:
    st.subheader("我的组合")
    st.warning("本页仅做持仓交叉验证，不产生任何买卖建议。")
    conn = db.db_conn()
    portfolio_path = ROOT / "config" / "portfolio.csv"
    if not portfolio_path.exists():
        st.error("缺少 config/portfolio.csv。")
        conn.close()
        return

    results = cross_check(conn, portfolio_path)
    if not results:
        st.info("组合配置为空。请在 config/portfolio.csv 中填写 ticker,weight。")
        conn.close()
        return

    st.dataframe(
        [
            {
                "Ticker": r.ticker,
                "跟踪机构": r.tracked_holders,
                "高质量机构": r.high_quality_holders,
                "共识分": r.consensus_score,
                "1Q": r.trend_1q,
                "4Q": r.trend_4q,
                "8Q": r.trend_8q,
                "NEW": r.notable_new,
                "EXIT": r.notable_exit,
                "证据方向": r.evidence,
            }
            for r in results
        ],
        width='stretch',
    )
    st.caption("证据方向：EVIDENCE_STRENGTHENS / EVIDENCE_WEAKENS / NO_MEANINGFUL_CHANGE / INSUFFICIENT_EVIDENCE / UNRESOLVED。")
    conn.close()


run()


