# 产品方法论与限制 / Product Methodology and Limitations

## 数据来源 / Data Source

系统通过自己的采集与验证流程读取 SEC Form 13F。13F 披露的是机构投资管理人的已报告多头持仓。

The system reads SEC Form 13F through its own ingestion and validation pipeline.
Form 13F discloses reported long positions of institutional investment managers.

## 页面展示什么 / What the Dashboard Shows

页面展示已报告多头持仓的股数、报告价值、组合权重，以及由确定性规则计算的新增、增持、减持、退出和未变化。页面还展示连续报告活动、披露新鲜度、修订状态、证券身份质量和数据质量。

The dashboard shows shares, reported values, portfolio weights, and deterministic
NEW, ADD, REDUCE, EXIT, and UNCHANGED facts. It also shows repeated reported
activity, filing freshness, amendments, security identity quality, and data quality.

## 时间延迟 / Reporting Delay

报告季度和 filing 日期是两个不同的事实，页面会同时展示。13F 最长可以在季度结束后 45 天提交，所以这些数据不代表实时仓位。

The report period and filing date are separate facts and appear together. A 13F
can be filed up to 45 days after quarter end, so the data never represents a
real-time position.

## 已知限制 / Known Limitations

- 13F 不披露空头仓位。 / Short positions are not disclosed.
- 完整的对冲、衍生品、互换和期货背景不可见。 / Full hedge, derivative, swap, and futures context is unavailable.
- 精确交易日期和真实成本基础未知。 / Exact transaction dates and true cost basis are unknown.
- 保密处理可能隐藏持仓，当季未披露不能直接解释为不持有。 / Confidential treatment can hide holdings, so not disclosed does not mean not held.
- 修订文件会改变最新有效状态，系统保留来源链。 / Amendments can change the latest effective state, while the source chain remains available.
- 部分申报机构的数据可能陈旧，历史季度也可能不完整。 / Some filers may be stale or historically incomplete.
- 证券身份可能处于未解析、有歧义或有冲突状态，系统会显示这些状态，不会猜测。 / Security identities can be unresolved, ambiguous, or conflicting; the system shows these states and never guesses.
- 中文公司和机构名称来自项目展示词表，只帮助阅读。SEC 英文法定名与 CUSIP 仍是身份依据。 / Chinese company and manager names come from a presentation glossary for readability only. SEC legal names and CUSIPs remain authoritative.

## 已冻结的历史研究结果 / Frozen Historical Research Result

- 连续两个或三个季度的行为在研究层提高了描述性结构稳定性。 / Two-quarter or three-quarter persistence improved descriptive structural stability in the research layer.
- 已冻结的 v0.3 结果验证没有证明这些持续行为带来增量经济结果。 / The frozen v0.3 outcome validation did not show an incremental economic outcome from that persistence.
- 预测研究停止规则已触发。 / The predictive research stop rule is triggered.
- 产品继续提供可核验证据和中性的机构活动计数，不据此作出预测。 / The product continues to provide verifiable evidence and neutral institutional activity counts without turning them into predictions.
