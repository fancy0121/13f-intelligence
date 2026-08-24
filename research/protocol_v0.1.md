# Signal Research & Anti-Overfitting Harness — Protocol v0.1 (PRE-REGISTERED)

> 本文档在查看任何 holdout 结果之前冻结。冻结后不得因 holdout 表现修改
> 本文档；任何方法论变更只能进入 NEXT_EXPERIMENT_VERSION。

## 0. Purpose

使用现有真实 SEC 13F 数据（FACT LAYER）回答：

> 复杂规则是否真的比最简单 baseline（A0）多提供稳定、可复现、增量信息？

如果答案是否定的，**拒绝复杂规则就是成功结果**。

## 1. Data Snapshot (frozen at protocol write)

- Source: SQLite `data/thirteenf.db`（由 raw SEC filings 确定性重建）
- Managers: 29（VERIFIED / VERIFIED_WITH_SCOPE）
- Filings: 339（含 12 amendments）
- Holdings: 600,173
- Position changes: 336,175
- Report periods: 2021-03-31 … 2026-06-30；共同覆盖主窗口
  **2023-09-30 … 2026-06-30（12 个季度）**
- Securities: 13,005（全部 CUSIP 级，ticker 未映射不阻塞研究）

## 2. Canonical Identity

- 研究层 canonical identity = **CUSIP / security_id**。
- Ticker 仅用于展示；ticker mapping 不完整**不阻塞**研究。
- 主实验限定 `put_call=''`（普通股多头）；PUT/CALL 行不计入主信号，
  但在 coverage 与 mapping/options 审计中报告。

## 3. Three Layers

```text
FACT LAYER        (SEC filings, holdings, changes, weights, quality metadata)
RESEARCH LAYER    (A0-A4 experiments; all outputs marked EXPERIMENTAL)
APPROVED PRODUCT  (frozen this phase; only CANDIDATE_FOR_PRODUCT_APPROVAL)
```

- Research 只读 FACT LAYER；不反写 holdings/raw。
- Research 结果不得静默进入 production。

## 4. Hypotheses (pre-registered)

- H_A1: persistence（同方向连续 2Q/3Q）相对 A0 提供稳定增量信息。
- H_A2: portfolio-weight 行为（shares↑/weight↑ vs shares↑/weight↓ 等）相对
  A0/A1 提供增量价值。
- H_A3: 数据驱动的 manager characteristics（turnover / concentration /
  position count / holding persistence / filing continuity / options proxy）
  分桶后改善信号稳定性或增量信息。
- H_A4 (optional): 简单 strategy-diversity 计数提供额外信息。

## 5. Experiment Variants

### A0 — TRUE MINIMUM BASELINE

对每个 (security_id, report_period)，eligible manager（该期有 position change）
的普通股动作**等权**计数：

- counts: NEW, ADD, REDUCE, EXIT, UNCHANGED
- `net_directional = (NEW + ADD) - (REDUCE + EXIT)`
- 不使用 manager quality / ticker / portfolio / persistence。

### A1 — Persistence

仅增加时间持续性（不增加 manager quality）：

- 变体 A1_2Q：对 (manager, security)，连续 2 个相邻 quarter 同方向
  （ADD/NEW 视为同向+，REDUCE/EXIT 视为同向−）才计入该期信号。
- 变体 A1_3Q：同上，3 个 quarter。

### A2 — Portfolio Weight Confirmation

在 A0（或明确版本）基础上增加 weight 行为。对每个 (manager, security, period)
用 `shares` 与 `portfolio_weight` 联合分类：

- `UP_UP`    shares↑, weight↑
- `UP_DOWN`  shares↑, weight↓   （明确区分，不当作 conviction 增强）
- `DOWN_DOWN` shares↓, weight↓
- `DOWN_UP`  shares↓, weight↑
- `NEW_WEIGHT` NEW 且 weight_now 有值
- `EXIT`
- 其余 UNCHANGED

主实验使用 net weight-direction score：
`net_weight_direction = (#UP_UP + #NEW_WEIGHT) - (#DOWN_DOWN + #EXIT)`
`UP_DOWN` 单独报告（divergence rate），不计入 +。

### A3 — Manager Characteristics

仅从已有 13F 数据计算 manager 特征（**不使用**主观“聪明度”）：

- `turnover_proxy`：跨期 holdings 集合差异 / 平均持仓数
- `concentration_top10`：Top-10 value / total value
- `position_count`：平均持仓数
- `holding_persistence`：同 security 连续持有比例
- `filing_continuity`：有效 filing 连续 quarter 数
- `options_proxy`：PUT/CALL 行占比

分桶：每特征按 cross-sectional 三分位 → LOW / MEDIUM / HIGH（quantile buckets，
不用伪精确 0.873）。A3 主变体：按 `holding_persistence` 与 `filing_continuity`
的 LOW/MEDIUM/HIGH 分层，分别报告各 bucket 的 A2 指标；不做加权混合“聪明分”。

### A4 — Strategy Diversity (optional)

如实现：`number_of_strategy_groups` = 对某 (security, period) 有信号的 manager
中 distinct `strategy_type` 数（当前 production taxonomy 为空时用数据驱动 cohort：
turnover/options proxy 分桶作为 group proxy）。若实现成本高则标记
`NOT_EXECUTED_OPTIONAL`，不阻塞。

## 6. Information Time (leakage control)

- 每条观测使用 `information_available_date` = effective filing 的
  `filing_date`（13F-HR/A 视为 amendment 公开日）。
- **不得**把 `report_period` 当作信息已知日。
- 例：2026-06-30 holdings 于 2026-08-14 filing ⇒ 信息时间 2026-08-14。
- Outcome 起点 = information_available_date（如 outcome 可用）。

## 7. Time Split (deterministic chronological)

- 开发期：共同窗口**最早 8 个季度**（2023-09-30 … 2025-06-30）。
- Time holdout：**最近 4 个季度**（2025-09-30 … 2026-06-30）。
- 若某 security/manager 覆盖不足：该观测按可用历史计算并标记
  `INSUFFICIENT_HISTORY`，不人为挑选“正常季度”。
- 禁止因结果改变 split。
- 输出 `reports/research/time_split_manifest.csv`。

## 8. Manager Split (deterministic hash)

- 固定 seed：`MANAGER_SPLIT_SEED = "13f-research-v0.1-manager"`
- 规则：`int(sha256(f"{cik}:{seed}").hexdigest()[:8], 16) % 100 < 70`
  ⇒ development manager；否则 manager holdout（约 30%）。
- 不按名声/历史收益/实验结果调整。
- 输出 `reports/research/manager_split_manifest.csv`。

## 9. Security Split (deterministic hash)

- 固定 seed：`SECURITY_SPLIT_SEED = "13f-research-v0.1-security"`
- 规则：`int(sha256(f"{cusip}:{seed}").hexdigest()[:8], 16) % 100 < 80`
  ⇒ development security；否则 security holdout（约 20%）。
- 不因 ticker 知名度或后续表现调整。
- 输出 `reports/research/security_split_manifest.csv`。

## 10. Multi-Axis Evaluation

| ID | Definition |
|---|---|
| H0 | dev time × dev managers × dev securities |
| H1 | time holdout（dev managers × dev securities） |
| H2 | manager holdout（dev time × dev securities） |
| H3 | security holdout（dev time × dev managers） |
| H4 | combined hard holdout（time × manager × security），样本不足则 `INSUFFICIENT_SAMPLE` |

## 11. Metrics (pre-registered)

### Coverage

- eligible observations；signal-producing observations；insufficient-data rate
- manager coverage；security coverage；quarter coverage

### Stability

- quarter-to-quarter sign stability（相邻期 net signal 同号比例）
- signal persistence（同号连续期数分布）
- reversal rate（相邻期异号比例）
- manager-subsample variance；security-subsample variance；time-window variance

### Incremental Information

- A1 vs A0；A2 vs A0/A1；A3 vs A2；A4 vs simpler
- coverage delta；stability delta；variance delta
- directional agreement/disagreement（复杂规则改变结论的 case 列表）

### Cross-Holdout Robustness

- 每个 variant 在 H0-H3 分别报告；最终推荐依据**最弱 holdout**，不是最好。

## 12. Variance Gate

满足任一 ⇒ variant 标记 `UNSTABLE`：

- 不同 manager split 结果方向频繁翻转
- security subsample variance 高（pre-registered：信号方向在随机安全子样本
  ±30% 中翻转 > 20%）
- time holdout 与 development 结论明显相反
- 少数 manager 决定大部分结果（top-1 contributor share > 50%）

## 13. Dominance / Concentration Audit

- top contributor share；top-3 contributor share
- leave-one-manager-out sensitivity（移除单个 manager 后方向翻转比例）
- 若移除单个 manager 大量翻转 ⇒ `MANAGER_DOMINATED`

## 14. Sensitivity (pre-registered, no fishing)

仅测试：

- A1: persistence 2Q vs 3Q
- A2: 是否将 UP_DOWN 计为负（预注册：不计，单独报告）
- A3: quantile bucket boundary（三分位 vs 中位数二分的敏感性）
- 最低参与 manager 数：1 与 3

所有测试过的组合必须报告，不只展示赢家。

## 15. Missing-Data Treatment

- unresolved ticker：不阻塞（用 CUSIP）
- stale manager（最新 filing 较旧）：照常纳入但标记
- insufficient quarters：`INSUFFICIENT_HISTORY`
- 无 position change 的 security/period：不计入 eligible

## 16. Outcome Evaluation

- 仅当存在可靠历史价格源（无秘密、无付费、合理工程成本）时启用
  `research/outcomes` adapter。
- 当前无 approved provider ⇒
  `FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER`
- 不因缺价格源阻塞结构/stability/holdout/leakage 审计。

## 17. Promotion Criteria

仅当同时满足：

1. 相对前一简单版本有 coverage 或 stability 改善
2. 在 H0-H3 方向基本一致（尤其最弱 holdout 不反向）
3. 非 `UNSTABLE`
4. 非 `MANAGER_DOMINATED`
5. 无泄漏审计问题

才标 `CANDIDATE_FOR_PRODUCT_APPROVAL`。其余结论必须为
`SUPPORTED / WEAKLY_SUPPORTED / NO_INCREMENTAL_VALUE / UNSTABLE /
INSUFFICIENT_EVIDENCE / REJECTED_OR_REQUIRES_NEW_EXPERIMENT` 之一。

## 18. Multiple-Testing Discipline

- 记录 experiments attempted、metrics observed、selection rule。
- 变体数量 > 5 时标注 `MULTIPLE_TESTING_RISK`，不做未校正显著性声明。

## 19. Fixed Seeds

```text
MANAGER_SPLIT_SEED = "13f-research-v0.1-manager"
SECURITY_SPLIT_SEED = "13f-research-v0.1-security"
```

## 20. Deliverables

- `research/protocol_v0.1.md`（本文档）
- split manifests（time / manager / security）
- `reports/research/leakage_audit.md`
- `reports/research/experiment_comparison.md`
- `reports/research/holdout_results.md`
- `reports/research/variance_and_sensitivity.md`
- `reports/research/mapping_bias_audit.md`
- `reports/research/final_recommendation.md`
- machine-readable artifacts（CSV/JSON）
- `FINAL_RESEARCH_MANIFEST`

## 21. Release Status Semantics

- `ANTI_OVERFITTING_HARNESS_STATUS=DELIVERED`：所有核心 harness gates 满足
- `PRODUCT_METHODOLOGY_STATUS=NO_RULE_APPROVED`（默认；除非候选评审后提升）
- `REAL_WORLD_DECISION_UTILITY=PENDING`（不变）

---

PROTOCOL_FREEZE_VERSION=v0.1
