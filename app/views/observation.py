"""Real-use observation page (v0.5): status + start/finish + export.

Kept separate from the core evidence pages. Subjective utility flags are
entered by the user; the system never auto-fills them.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from thirteenf.product.observation import EPISODE_FIELDS, ObservationStore
from ui import T, display_code

OBS_DIR = ROOT / "data" / "real_use"

TARGET_TYPES = {
    T("证券", "Security"): "security",
    T("机构", "Manager"): "manager",
    T("组合", "Portfolio"): "portfolio",
}
FAMILIARITY = {
    display_code("UNKNOWN"): "UNKNOWN",
    T("熟悉", "Familiar"): "familiar",
    T("不熟悉", "Unfamiliar"): "unfamiliar",
}
BASELINE_METHODS = {
    display_code("UNKNOWN"): "UNKNOWN",
    T("手动查 SEC", "Manual SEC lookup"): "手动查 SEC",
    T("网页搜索", "Web search"): "网页搜索",
    T("既有知识", "Existing knowledge"): "既有知识",
    T("外部仪表盘", "External dashboard"): "外部仪表盘",
    T("原本没打算查", "Would not have checked"): "原本没打算查",
}
EFFORT_BUCKETS = {
    T("少于 5 分钟", "Under 5 minutes"): "<5",
    T("5–15 分钟", "5–15 minutes"): "5-15",
    T("15–30 分钟", "15–30 minutes"): "15-30",
    T("超过 30 分钟", "Over 30 minutes"): ">30",
    display_code("UNKNOWN"): "UNKNOWN",
}
MISUSE_RISKS = {
    display_code(code): code for code in ("NONE", "LOW", "MODERATE", "HIGH", "UNKNOWN")
}


def _store() -> ObservationStore:
    if os.environ.get("THIRTEENF_PUBLIC_MODE", "").strip().lower() in ("1", "true", "yes"):
        if "public_observation_store" not in st.session_state:
            st.session_state["public_observation_store"] = ObservationStore(None)
        return st.session_state["public_observation_store"]
    return ObservationStore(OBS_DIR)


def _csv_download(episodes: list[dict]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=EPISODE_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(episodes)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _counts(values: dict, labels: dict[str, str]) -> str:
    return "；".join(f"{label}: {values.get(code, 0)}" for code, label in labels.items())


def run() -> None:
    st.subheader(T("研究观察：真实使用效用记录（前瞻）", "Research Log: Prospective real-use utility record"))
    st.caption(
        "本页用于在你使用证据产品前先记录已知信息，避免事后重写认知。"
        "主观结论（是否发现新事实、是否改变下一步等）必须由你确认，系统不会自动填写。 / "
        "Record known information before using the evidence product to avoid hindsight "
        "rewriting. Subjective conclusions must be confirmed by you - never auto-filled."
    )
    store = _store()
    agg = store.aggregate()
    valid = agg["valid_episodes"]

    if valid < 20:
        st.warning(
            "INSUFFICIENT_OBSERVATION — 尚无足够的真实使用 episode，当前不给出任何真实世界效用结论。 / "
            "Not enough real-use episodes yet - no real-world utility conclusion is given."
        )
    c1, c2, c3 = st.columns(3)
    c1.metric("有效记录 / Valid episodes", f"{valid}/20")
    c2.metric("原始记录 / Raw episodes", agg["raw_episode_count"])
    c3.metric("唯一目标 / Unique targets", agg["unique_target_count"])
    st.write(
        f"- {T('场景分布', 'Scenarios')}: "
        f"{_counts(agg['scenario_breakdown'], {'security': T('证券', 'Security'), 'manager': T('机构', 'Manager'), 'portfolio': T('组合', 'Portfolio')})}；"
        f"{T('组合占比', 'Portfolio share')}: {agg['portfolio_share']:.0%}"
    )
    st.write(
        f"- {T('熟悉度', 'Familiarity')}: "
        f"{_counts(agg['familiarity_breakdown'], {'familiar': T('熟悉', 'Familiar'), 'unfamiliar': T('不熟悉', 'Unfamiliar'), 'UNKNOWN': display_code('UNKNOWN')})}；"
        f"{T('没有增量信息', 'No incremental information')}: "
        f"{int(agg['no_incremental_information_rate'] * valid)}"
    )
    st.write(
        f"- {T('误用风险', 'Misuse risk')}: "
        f"{_counts(agg['misuse_risk_counts'], {code: display_code(code) for code in ('NONE', 'LOW', 'MODERATE', 'HIGH', 'UNKNOWN')})}；"
        f"{T('产品设计诱发', 'Design-induced')}: {agg['product_design_induced_misuse']}"
    )

    st.divider()
    st.markdown("#### 开始一次研究检查（pre-use） / Start a research check (pre-use)")
    with st.form("obs_start"):
        ttype_label = st.selectbox(
            "目标类型 / Target type",
            list(TARGET_TYPES),
        )
        tid = st.text_input("目标标识 / Target ID（CUSIP / ticker / manager 名称）")
        tlabel = st.text_input("目标显示名（可选）/ Display name (optional)")
        fam_label = st.selectbox(
            "熟悉度 / Familiarity",
            list(FAMILIARITY),
        )
        q = st.text_area("我正在研究什么？ / What am I researching?", height=60)
        know = st.text_area("我已知道/相信什么？ / What do I already know/believe?", height=60)
        unc = st.text_area("我不确定什么？ / What am I unsure about?", height=60)
        nxt = st.text_area("如果没有这个工具，我下一步会怎么做？ / "
                           "What would I do next without this tool?", height=60)
        baseline_label = st.selectbox(
            "原本的信息获取方式 / Baseline method",
            list(BASELINE_METHODS),
        )
        submitted = st.form_submit_button("开始（保存 pre-use）/ Start (save pre-use)")
    if submitted:
        if not q.strip():
            st.error("请至少填写研究问题。 / Please fill in a research question.")
        else:
            ep = store.start_episode(
                {
                    "target_type": TARGET_TYPES[ttype_label],
                    "target_id": tid.strip(),
                    "target_label": tlabel.strip() or tid.strip(),
                    "is_portfolio_target": "true" if TARGET_TYPES[ttype_label] == "portfolio" else "false",
                    "familiarity_class": FAMILIARITY[fam_label],
                    "research_question": q.strip(),
                    "pre_use_knowledge": know.strip() or "UNKNOWN",
                    "pre_use_assumptions": "UNKNOWN",
                    "pre_use_uncertainties": unc.strip() or "UNKNOWN",
                    "planned_next_step": nxt.strip() or "UNKNOWN",
                    "baseline_method": BASELINE_METHODS[baseline_label],
                }
            )
            st.success(f"已开始 episode：{ep['episode_id']}（请先使用产品页面，再回来完成）/ "
                       f"Episode started: {ep['episode_id']} (use the product pages, then come back to finish)")

    st.divider()
    st.markdown("#### 完成研究检查（post-use）/ Finish a research check (post-use)")
    episodes = [e for e in store.episodes() if e.get("episode_validity") == "PENDING"]
    if not episodes:
        st.info("暂无待完成的 episode。 / No pending episodes.")
    else:
        labels = {f"{e['episode_id']} ({e.get('target_label', '')})": e["episode_id"] for e in episodes}
        with st.form("obs_finish"):
            sel = st.selectbox("选择 episode / Select episode", list(labels))
            c = st.columns(4)
            new_fact = c[0].checkbox("发现新事实 / New fact found")
            contradict = c[1].checkbox("看到未充分考虑的事实 / Contradicting fact seen")
            stale = c[2].checkbox("原有假设已陈旧 / Prior assumption stale")
            qrisk = c[3].checkbox("发现数据质量限制 / Quality risk found")
            c2 = st.columns(4)
            path = c2[0].checkbox("改变了下一步研究 / Research path changed")
            saved = c2[1].checkbox("节省了核验时间 / Verification time saved")
            noinc = c2[2].checkbox("没有增量信息 / No incremental info")
            design = c2[3].checkbox("界面诱导了预测性理解（产品缺陷）/ UI induced forward-looking reading (defect)")
            effort_label = st.selectbox(
                "估算节省的核验时间 / Estimated time saved",
                list(EFFORT_BUCKETS),
            )
            misuse_label = st.selectbox(
                "误用风险 / Misuse risk",
                list(MISUSE_RISKS),
            )
            notes = st.text_area("备注（可选）/ Notes (optional)")
            submitted2 = st.form_submit_button("完成（保存 post-use）/ Finish (save post-use)")
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
                    "estimated_manual_effort_bucket": EFFORT_BUCKETS[effort_label],
                    "misuse_risk": MISUSE_RISKS[misuse_label],
                    "product_design_issue": str(design).lower(),
                    "notes": notes,
                },
            )
            st.success("已保存 post-use；episode 有效性已按协议判定。 / Post-use saved; validity judged by protocol.")
            st.rerun()

    st.divider()
    episodes_for_download = store.episodes()
    c1, c2 = st.columns(2)
    c1.download_button(
        "下载 CSV / Download CSV",
        data=_csv_download(episodes_for_download),
        file_name="13f-research-episodes.csv",
        mime="text/csv",
        use_container_width=True,
    )
    c2.download_button(
        "下载 JSON / Download JSON",
        data=json.dumps(episodes_for_download, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="13f-research-episodes.json",
        mime="application/json",
        use_container_width=True,
    )


run()
