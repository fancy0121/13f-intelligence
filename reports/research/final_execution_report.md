# 13F Institutional Intelligence System
# Signal Research & Anti-Overfitting Harness — Final Report

> Generated: 2026-08-24
> Mode: AUTONOMOUS OBJECTIVE EXECUTION（目标文件完整读取，无截断）

## Repository

- Baseline SHA: `20a4ffef05a69e00a21bcf2caea08fb52c08f0ac`
- Protocol freeze SHA: `69e728f0e1394c953d752add7d5f4a2cedcf7bea`
- Final SHA: `b26efa3`（本报告提交后以 `git log` 为准）
- Commits: baseline → protocol freeze → harness+tests → artifacts+reports →
  final report（每 commit coherent，protocol freeze 可单独识别）
- Git status: clean（`## master`）

## Data Snapshot

| Item | Value |
|---|---|
| Managers | 29（VERIFIED / VERIFIED_WITH_SCOPE） |
| Filings | 339（含 12 amendments） |
| Holdings | 600,173 |
| Position transitions | 336,175 |
| Quarter coverage | 2021-03-31 … 2026-06-30；研究窗口冻结为 2023-09-30 … 2026-06-30（12Q） |
| Exclusions | 无按结果剔除；stale manager 保留并标记 |

## Tests

- Original production tests: 44 passed（parser/amendments/changes/weight/
  consensus/trends/quality/portfolio/security/database/golden fixtures/
  module boundaries）
- New research tests: 20 passed（splits / information time / experiments /
  metrics / negative tests）
- Total: **64 passed**
- Failures discovered and fixed: 2（time-split window bug → protocol window；
  A3 bucket index bug → manager_id index；numpy JSON serialization → sanitize）

## Splits

- Development: 2023-09-30 … 2025-06-30（8 季度）
- Time holdout: 2025-09-30 … 2026-06-30（4 季度）
- Manager split: SHA256(CIK + seed)，~70/30（manifests 提交）
- Security split: SHA256(CUSIP + seed)，~80/20（manifests 提交）
- Seeds: 固定于 protocol（`MANAGER_SPLIT_SEED` / `SECURITY_SPLIT_SEED`）
- H4 combined holdout 样本足够（~11.9k obs），未触发 INSUFFICIENT_SAMPLE

## Leakage Audit

逐项结论见 `reports/research/leakage_audit.md`。摘要：

- 时间泄漏：LOW（info_date = effective filing_date，amendment-aware）
- Portfolio / ticker / outcome / holdout 泄漏：LOW 或无
- Survivorship：KNOWN（29 家为人工精选 universe，非全体 13F 随机样本）
- 无严重泄漏 → Gate B PASS

## Experiments

### A0
等权 action counts（NEW/ADD/REDUCE/EXIT/UNCHANGED + net_directional）。
H0 eligible 75,385；stability 0.315；coverage 完整。

### A1（vs A0）
2Q persistence：stability 0.577（dev，+0.26），time 0.637；eligible 降至 23,536
（−69%）。
3Q persistence：stability 0.789（dev），time 0.885；eligible 降至 7,381（−90%）。

### A2（vs A0/A1）
net weight-direction 在 dev 0.291（略低于 A0 0.315），time 0.276；无增量。

### A3（vs A2）
分桶描述性结果：filing_continuity LOW 0.220 / MEDIUM 0.333 / HIGH 0.294；
avg_concentration HIGH 0.426 但样本 1,468，INSUFFICIENT_SAMPLE。

### A4
`NOT_EXECUTED_OPTIONAL`（protocol 允许；未阻塞）。

## Holdout Performance

| Variant | Dev | Time | Manager | Security | Combined |
|---|---|---|---|---|---|
| A0 stability | 0.315 | 0.308 | 0.348 | 0.315 | 0.400 |
| A1_2Q stability | 0.577 | 0.637 | 0.722 | 0.575 | 0.670 |
| A1_3Q stability | 0.789 | 0.885 | 0.839 | 0.776 | 0.870 |
| A2 stability | 0.291 | 0.276 | 0.268 | 0.294 | 0.364 |

方向一致：无 dev-good/holdout-bad 反转。推荐依据最弱 holdout（time）。

## Variance

- Leave-one-manager-out flip fraction：A0 ~0.000016、A1_2Q 0.012、A1_3Q 0.006、
  A2 ~0.000008 → 无 MANAGER_DOMINATED
- 无 UNSTABLE 标志（方向跨 split 一致）
- 敏感性：仅预注册参数（2Q vs 3Q、bucket 边界、UP_DOWN 处理），全部报告

## Outcome Evaluation

`FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER`
（无经批准的价格源；未抓取不可靠行情；不阻塞结构验证）

## Complexity Verdict

- Justified: A1 2Q persistence（跨 split 稳定性显著提升，代价 coverage 下降，
  需外部评审后决定是否进入产品层）
- Not justified: A2（无增量）、A3 精确评分（无证据）、strategy diversity

## What We Should Keep

- A0 fact counts（FACT LAYER 字段）
- A1 2Q persistence 作为 EXPERIMENTAL filter
- Research harness（splits/manifests/leakage audit/CLI）

## What We Should Delete / Not Build

- 不做精确 manager signal_quality 分数
- 不做 normalized 0–100 consensus 作为头条数字
- 不把 A2 weight-direction 提升为产品信号
- 不做 strategy diversity / clustering / ML 相关图

## Candidate Product Rules

- 无规则在本阶段自动晋升。A1 2Q persistence 仅列为
  `CANDIDATE_FOR_PRODUCT_APPROVAL`（待外部审计 + 更长历史），不作生产部署。

## Gates

- Protocol Integrity: **PASS**（冻结 commit 69e728f；no post-hoc tuning）
- Leakage: **PASS**（无严重泄漏；残差已记录）
- Reproducibility: **PASS**（双跑产物哈希一致；仅 manifest 时间戳不同）
- Baseline Comparison: **PASS**（A0 KEEP；A1_2Q WEAKLY_SUPPORTED；A2/A3
  NO_INCREMENTAL_VALUE；A1_3Q EXPERIMENT_AGAIN）
- Holdout Robustness: **PASS**（方向跨 split 一致）
- Simplicity: **PASS**（最简存活模型 A0；未晋升复杂规则）
- Real-World Decision Utility: **PENDING**（保持不变）

## Remaining Weaknesses

- 仅 12 季度历史；A1_3Q 覆盖率过低（~10%）
- 29 家 universe 非随机全体样本（UNIVERSE LIMITATION）
- A3 特征为 full-period，非 point-in-time
- 无行情 outcome 评价（无 approved provider）

## Recommended Next Step

下一 reporting cycle 后：

1. 用新增季度重跑同一 protocol（不改阈值/split/种子）；
2. 检验 A1 2Q persistence 在更长时间窗的稳定性与覆盖率；
3. 若仍稳定，进入外部 product review（候选规则）；
4. 否则保留 A0 作为唯一事实层信号。

## Release Status

```
ANTI_OVERFITTING_HARNESS_STATUS=DELIVERED
PRODUCT_METHODOLOGY_STATUS=NO_RULE_APPROVED
FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER
REAL_WORLD_DECISION_UTILITY=PENDING
```

