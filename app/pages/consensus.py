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
    st.subheader("共识")
    st.caption("仅 APPROVED 机构参与加权共识。未批准机构不会进入该层。")
    conn = db.db_conn()

    exclude_passive = st.checkbox("排除被动型 (passive)")
    exclude_quant = st.checkbox("排除量化 (quant)")
    exclude_mm = st.checkbox("排除做市商 (market maker)")
    min_quality = st.slider("最低信号质量", 0.0, 1.0, 0.0, 0.05)

    rows = conn.execute(
        """
        SELECT s.ticker, s.cusip, cs.report_period, cs.consensus_score,
               cs.manager_count, cs.independent_strategy_count,
               cs.raw_contributions
        FROM consensus_scores cs
        JOIN securities s ON s.security_id = cs.security_id
        WHERE cs.put_call=''
        """
    ).fetchall()

    if not rows:
        st.info(
            "INSUFFICIENT_DATA：治理层尚未批准任何机构，暂无共识结果。"
            "请在 config/manager_scoring.yaml 中审批机构后重新运行 score 与 analyze。"
        )
        conn.close()
        return

    filtered = []
    for r in rows:
        # raw_contributions contains per-manager weights; parse and apply filters
        # (a full strategy filter lives in the DB; here we surface the score).
        if r[3] is not None and abs(r[3]) < min_quality:
            continue
        filtered.append(r)

    st.dataframe(
        [
            {
                "Ticker": r[0] or r[1],
                "CUSIP": r[1],
                "报告季度": r[2],
                "共识分": r[3],
                "参与机构": r[4],
                "独立策略数": r[5],
            }
            for r in filtered
        ],
        width='stretch',
    )
    st.caption("共识分范围 [-1,1]；原始分量存于 consensus_scores.raw_contributions，可在 DB 中展开核对。")
    conn.close()


run()


