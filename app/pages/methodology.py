from __future__ import annotations

from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "product_methodology_and_limitations.md"


def _h(zh: str, en: str) -> str:
    return f"### {zh} <span style='color:#5B7186;font-size:.8em;font-weight:500;'>/ {en}</span>"


def run() -> None:
    st.subheader("方法论与限制 / Methodology & Limitations")
    st.markdown(
        """
        ### 这份看板是什么？ <span style='color:#5B7186;font-size:.8em;font-weight:500;'>/ What is this dashboard?</span>

        这份看板展示的是 **SEC Form 13F 披露的机构多头持仓事实**。每季度，大型机构要向 SEC 报告
        他们持有哪些美国证券、持有多少股、报告价值多少。看板把这些原始披露整理成：

        - **NEW**：某机构第一次报告持有某只证券（新增建仓）*— first reported position*。
        - **ADD**：某机构相比上一季度增加了持有股数（增持）*— shares increased vs prior quarter*。
        - **REDUCE**：某机构相比上一季度减少了持有股数（减持）*— shares decreased vs prior quarter*。
        - **EXIT**：某机构不再报告持有某只证券（退出）*— no longer reported*。
        - **UNCHANGED**：持有股数没有报告变化 *— no reported change*。
        - **重复活动**：同一机构连续两个或更多报告季度报告同方向（例如连续增持）
          *— same direction for ≥2 consecutive quarters*。
        - **组合权重**：该证券占该机构报告总市值的比例 *— share of reported total value*。

        ### 为什么这不是股票推荐？ <span style='color:#5B7186;font-size:.8em;font-weight:500;'>/ Why is this not a stock pick?</span>

        13F 只看得到 **多头持仓**。它看不到 *13F only shows long holdings. It cannot see*：

        - 空头仓位 *short positions*
        - 衍生品、期权、期货、对冲 *derivatives, options, futures, hedges*
        - 确切的买入/卖出时间 *exact purchase/sale timing*
        - 买入成本 *cost basis*
        - 机构是否因为保密申请而未披露某些持仓 *confidential-treatment omissions*

        而且 13F 允许最长 45 天延迟。所以「机构增持」只是一个**已披露事实**，不是
        「这家公司会涨」的结论。本项目曾做过严格的研究验证：连续 2 或 3 个季度的机构
        行为，没有被证明带来增量经济价值。因此看板只展示证据，不做预测。

        ### 你需要注意的限制 <span style='color:#5B7186;font-size:.8em;font-weight:500;'>/ Limitations to keep in mind</span>

        - 数据有延迟（报告季度 ≠ 实时持仓）*data is delayed (report quarter ≠ real-time)*。
        - 未解析的证券身份会明确标出（UNRESOLVED / AMBIGUOUS / CONFLICT），系统不会猜
          *unresolved identities are explicit; the system never guesses*。
        - 修订（amendment）会更新最新有效状态，来源链保留 *amendments update effective state; source chain kept*。
        - 保密处理可能使「当季未披露」不等于「不持有」
          *confidential treatment means "not disclosed" ≠ "not held"*。
        """
    )
    st.divider()
    if DOC.exists():
        st.markdown(f"#### 更详细的说明（面向研究者） <span style='color:#5B7186;font-size:.8em;font-weight:500;'>/ Detailed notes (for researchers)</span>")
        st.markdown(DOC.read_text(encoding="utf-8"))
    else:
        st.info("方法论文档缺失 / Methodology document missing.")


run()
