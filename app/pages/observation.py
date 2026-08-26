"""Real-use observation page (v0.5): status + start/finish + export.

Kept separate from the core evidence pages. Subjective utility flags are
entered by the user; the system never auto-fills them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.observation import ObservationStore

OBS_DIR = ROOT / "data" / "real_use"


def _store() -> ObservationStore:
    return ObservationStore(OBS_DIR)


def run() -> None:
    st.subheader("研究观察 - 真实使用效用记录（前瞻）")
    st.caption("本页用于在你使用证据产品前先记录已知信息，避免事后重写认知。"
               "主观结论（是否发现新事实、是否改变下一步等）必须由你确认，系统不会自动填写。")
    store = _store()
    agg = store.aggregate()
    valid = agg["valid_episodes"]

    if valid < 20:
        st.warning("INSUFFICIENT_OBSERVATION — 尚无足够的真实使用 episode，"
                   "当前不给出任何真实世界效用结论。")
    c1, c2, c3 = st.columns(3)
    c1.metric("有效 episode", f"{valid}/20")
    c2.metric("原始 episode", agg["raw_episode_count"])
    c3.metric("唯一目标", agg["unique_target_count"])
    st.write(f"- 场景分布：{agg['scenario_breakdown']}；组合占比：{agg['portfolio_share']:.0%}")
    st.write(f"- 熟悉度：{agg['familiarity_breakdown']}；"
             f"NO_INCREMENTAL_INFORMATION 计数："
             f"{int(agg['no_incremental_information_rate'] * valid)}")
    st.write(f"- misuse：{agg['misuse_risk_counts']}；"
             f"产品设计诱发：{agg['product_design_induced_misuse']}")

    st.divider()
    st.markdown("#### 开始一次研究检查（pre-use）")
    with st.form("obs_start"):
        ttype = st.selectbox("目标类型", ["security", "manager", "portfolio"])
        tid = st.text_input("目标标识（CUSIP / ticker / manager 名称）")
        tlabel = st.text_input("目标显示名（可选）")
        fam = st.selectbox("熟悉度", ["UNKNOWN", "familiar", "unfamiliar"])
        q = st.text_area("我正在研究什么？", height=60)
        know = st.text_area("我已知道/相信什么？", height=60)
        unc = st.text_area("我不确定什么？", height=60)
        nxt = st.text_area("如果没有这个工具，我下一步会怎么做？", height=60)
        baseline = st.selectbox("原本的信息获取方式",
                                ["UNKNOWN", "手动查 SEC", "网页搜索", "既有知识", "外部仪表盘", "原本没打算查"])
        submitted = st.form_submit_button("开始（保存 pre-use）")
    if submitted:
        if not q.strip():
            st.error("请至少填写研究问题。")
        else:
            ep = store.start_episode(
                {
                    "target_type": ttype,
                    "target_id": tid.strip(),
                    "target_label": tlabel.strip() or tid.strip(),
                    "is_portfolio_target": "true" if ttype == "portfolio" else "false",
                    "familiarity_class": fam,
                    "research_question": q.strip(),
                    "pre_use_knowledge": know.strip() or "UNKNOWN",
                    "pre_use_assumptions": "UNKNOWN",
                    "pre_use_uncertainties": unc.strip() or "UNKNOWN",
                    "planned_next_step": nxt.strip() or "UNKNOWN",
                    "baseline_method": baseline,
                }
            )
            st.success(f"已开始 episode：{ep['episode_id']}（请先使用产品页面，再回来完成）")

    st.divider()
    st.markdown("#### 完成研究检查（post-use）")
    episodes = [e for e in store.episodes() if e.get("episode_validity") == "PENDING"]
    if not episodes:
        st.info("暂无待完成的 episode。")
    else:
        labels = {f"{e['episode_id']} ({e.get('target_label', '')})": e["episode_id"] for e in episodes}
        with st.form("obs_finish"):
            sel = st.selectbox("选择 episode", list(labels))
            c = st.columns(4)
            new_fact = c[0].checkbox("发现新事实")
            contradict = c[1].checkbox("看到未充分考虑的事实")
            stale = c[2].checkbox("原有假设已陈旧")
            qrisk = c[3].checkbox("发现数据质量限制")
            c2 = st.columns(4)
            path = c2[0].checkbox("改变了下一步研究")
            saved = c2[1].checkbox("节省了核验时间")
            noinc = c2[2].checkbox("没有增量信息")
            design = c2[3].checkbox("界面诱导了预测性理解（产品缺陷）")
            effort = st.selectbox("估算节省的核验时间", ["<5", "5-15", "15-30", ">30", "UNKNOWN"])
            misuse = st.selectbox("misuse 风险", ["NONE", "LOW", "MODERATE", "HIGH", "UNKNOWN"])
            notes = st.text_area("备注（可选）")
            submitted2 = st.form_submit_button("完成（保存 post-use）")
        if submitted2:
            store.finish_episode(
                labels[sel],
                {
                    "new_fact_found": str(new_fact).lower(),
                    "contradicting_fact_found": str(contradict).lower(),
                    "stale_assumption_corrected": str(stale).lower(),
                    "quality_risk_discovered": str(qrisk).lower(),
                    "research_path_changed": str(path).lower(),
                    "research_time_saved": str(saved).lower(),
                    "no_incremental_information": str(noinc).lower(),
                    "estimated_manual_effort_bucket": effort,
                    "misuse_risk": misuse,
                    "product_design_issue": str(design).lower(),
                    "notes": notes,
                },
            )
            st.success("已保存 post-use；episode 有效性已按协议判定。")
            st.rerun()

    st.divider()
    if st.button("导出 episode（CSV + JSON）"):
        store.export_csv(ROOT / "reports" / "product" / "real_use_episodes.csv")
        store.export_json(ROOT / "reports" / "product" / "real_use_episodes.json")
        st.success("已导出到 reports/product/real_use_episodes.csv/.json")


run()

