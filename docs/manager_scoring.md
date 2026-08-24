# Manager Scoring — 机构评分治理 (v0.1)

## 治理约束（不可改）

- **禁止默认中性评分**。未批准 manager 必须 `signal_quality = NULL`，
  `scoring_status = NOT_APPROVED`，不得进入 Weighted Consensus、high-quality
  manager count 或 governed consensus interpretation。
- 不制造未经验证的伪精确分数（如 0.91 / 0.87）。
- 最终分类必须 versioned、documented、reviewable、sensitivity-testable。

## 两个分析层

| 层 | 参与者 | 内容 |
|---|---|---|
| Objective Layer | 所有 manager | holdings、NEW/ADD/REDUCE/EXIT、share change、portfolio weight |
| Governed Interpretation Layer | 仅 APPROVED | weighted consensus、high-quality count、governed interpretation |

## v0.1 分层

粗粒度、可解释分层（`config/manager_scoring.yaml`）：

| Tier | consensus 权重 | 含义 |
|---|---|---|
| HIGH | 1.0 | 高质量、可解释信号 |
| MEDIUM | 0.7 | 中等质量信号 |
| LOW | 0.4 | 低质量信号 |
| NON_SIGNAL | 0.0 | 无信号贡献（如被动指数/做市商） |

## 评分维度（治理输入）

- strategy_type
- turnover / concentration
- passive exposure
- derivatives dependence
- 13F representativeness
- investment horizon
- replicability
- signal quality

## 变更流程

1. 修改 `config/manager_scoring.yaml`（含 tier、strategy_type、rationale）。
2. bump `methodology_version`。
3. `python -m thirteenf.cli score` 应用。
4. `python -m thirteenf.cli analyze` 重算 consensus/trend。
5. 敏感性测试：权重 ±20% 扰动，验证共识方向稳定。
6. 更新本文档与 reports。

## 当前状态

v0.1 交付时 22 家 VERIFIED 机构全部为 `NOT_APPROVED`，治理解释层为空——这是刻意的
保守状态：未经治理审批，系统不输出任何共识结论。
