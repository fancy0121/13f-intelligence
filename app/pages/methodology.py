from __future__ import annotations

from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "product_methodology_and_limitations.md"


def run() -> None:
    st.subheader("方法论与限制")
    st.markdown(
        """
        ### 这份看板是什么？

        这份看板展示的是 **SEC Form 13F 披露的机构多头持仓事实**。每季度，大型机构要向 SEC 报告
        他们持有哪些美国证券、持有多少股、报告价值多少。看板把这些原始披露整理成：

        - **NEW**：某机构第一次报告持有某只证券（新增建仓）。
        - **ADD**：某机构相比上一季度增加了持有股数（增持）。
        - **REDUCE**：某机构相比上一季度减少了持有股数（减持）。
        - **EXIT**：某机构不再报告持有某只证券（退出）。
        - **UNCHANGED**：持有股数没有报告变化。
        - **重复活动**：同一机构连续两个或更多报告季度报告同方向（例如连续增持）。
        - **组合权重**：该证券占该机构报告总市值的比例。

        ### 为什么这不是股票推荐？

        13F 只看得到 **多头持仓**。它看不到：

        - 空头仓位
        - 衍生品、期权、期货、对冲
        - 确切的买入/卖出时间
        - 买入成本
        - 机构是否因为保密申请而未披露某些持仓

        而且 13F 允许最长 45 天延迟。所以「机构增持」只是一个**已披露事实**，不是
        「这家公司会涨」的结论。本项目曾做过严格的研究验证：连续 2 或 3 个季度的机构
        行为，没有被证明带来增量经济价值。因此看板只展示证据，不做预测。

        ### 你需要注意的限制

        - 数据有延迟（报告季度 ≠ 实时持仓）。
        - 未解析的证券身份会明确标出（UNRESOLVED / AMBIGUOUS / CONFLICT），系统不会猜。
        - 修订（amendment）会更新最新有效状态，来源链保留。
        - 保密处理可能使「当季未披露」不等于「不持有」。
        """
    )
    st.divider()
    if DOC.exists():
        st.markdown("#### 更详细的说明（面向研究者）")
        st.markdown(DOC.read_text(encoding="utf-8"))
    else:
        st.info("方法论文档缺失。")


run()
