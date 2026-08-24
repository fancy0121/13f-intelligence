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
    st.subheader("总览")
    conn = db.db_conn()
    period = db.latest_period(conn)
    if not period:
        st.info("暂无 filing 数据。请先运行 normalize 与 analyze。")
        conn.close()
        return

    updated, total = db.manager_coverage(conn, period)
    c1, c2, c3 = st.columns(3)
    c1.metric("最新报告季度", period)
    c2.metric("机构更新覆盖", f"{updated}/{total}")
    c3.metric("未解析证券映射", db.unresolved_count(conn))

    st.divider()
    st.markdown("#### 数据质量状态")
    q = db.quality_summary(conn)
    if not q:
        st.success("未发现数据质量事件。")
    else:
        for event_type, severity, cnt in q:
            label = "⚠️" if severity == "WARN" else "❌"
            st.write(f"{label} {event_type}: {cnt}")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 显著增持 (ADD)")
        for row in db.notables(conn, period, "ADD", 10):
            st.write(f"`{row[0] or row[1]}` · {row[3]} · 变化 {row[4]:+.1%}" if row[4] else f"`{row[0] or row[1]}` · {row[3]}")
    with col_b:
        st.markdown("#### 显著减持 (REDUCE)")
        for row in db.notables(conn, period, "REDUCE", 10):
            st.write(f"`{row[0] or row[1]}` · {row[3]} · 变化 {row[4]:+.1%}" if row[4] else f"`{row[0] or row[1]}` · {row[3]}")

    st.divider()
    st.markdown("#### 共识反转 (REVERSAL)")
    rev = db.consensus_reversals(conn)
    if not rev:
        st.info("暂无共识反转（治理层尚未批准任何机构，或无数据）。")
    else:
        for r in rev:
            st.write(f"`{r[0] or r[1]}` · {r[2]} · {r[3]} ({r[4]})")

    st.caption("说明：13F 仅披露多头、可辨识证券仓位；不披露空头、衍生品、成本与精确交易时机。")
    conn.close()


run()

