# Methodology — 13F 分析方法论 (v0.1)

> 中文解释 + 英文标准术语。本文档由 `config/methodology.yaml` 中的
> `methodology_version` 治理；任何规则变更必须 bump version、重算、重测。

## 1. 13F 的含义

Form 13F（13F-HR / 13F-HR/A）是 SEC 要求的机构季度持仓披露。它只包含：

- 报告期的多头、可辨识证券仓位（common stock、options 的 PUT/CALL 等）；
- 每只证券的 CUSIP、issuer、title of class、value（美元）、shares。

它**不包含**：空头、大部分衍生品、完整基金组合、精确成交时间、精确成本、投资论点。

## 2. Position Change Rules

对每个 `(manager, security, put_call, report_period)` 与上一有效季度对比：

| change_type | 条件 |
|---|---|
| NEW | 本期存在，上期不存在 |
| EXIT | 本期不存在，上期存在 |
| ADD | 两期存在且 `shares_now > shares_prev` |
| REDUCE | 两期存在且 `shares_now < shares_prev` |
| UNCHANGED | 两期存在且 `shares_now == shares_prev` |

派生字段：

- `share_change = shares_now - shares_prev`
- `share_change_pct = share_change / shares_prev`（分母为 0 → NULL）
- `portfolio_weight = value / sum(value)`（denominator 为该 filing 全部披露行）
- `weight_change = weight_now - weight_prev`

**Shares 与 Weight 分离**：shares 增加但 portfolio weight 下降时，change_type 仍为
ADD，但 `weight_change < 0` 被保留展示，禁止解释为 conviction strengthening。

**Amendment 语义**：同一 (manager, report_period) 下，13F-HR/A 取代原 13F-HR；
原始 filing 永不删除，分析层只使用有效版本。新 amendment 入库后需重算。

## 3. Weighted Consensus

仅 `scoring_status=APPROVED` 的 manager 参与（Governed Interpretation Layer）。

```
consensus = Σ (weight_m × significance_m × change_score_m)
          / Σ (weight_m × significance_m)
```

- `weight_m`：治理评分（tier 对应权重，见 manager_scoring）。
- `significance_m`：默认 `min(weight_prev, weight_now)`（可配置）。
- `change_score_m ∈ [-1,1]`：EXIT=-1、NEW=1、ADD/REDUCE 按 `tanh(pct/0.5)` 缩放、
  UNCHANGED=0。
- 原始分量存 `consensus_scores.raw_contributions`（JSON），可逐项核对。
- 分数范围 [-1,1]；UI 的 [-100,100] 只是显示归一化，不改变原始语义。

## 4. Trend

在 consensus 序列上按 1Q / 4Q / 8Q 窗口计算：

- `STRENGTHENING`：窗口均值 > 阈值
- `WEAKENING`：窗口均值 < -阈值
- `STABLE`：|均值| ≤ 阈值
- `REVERSAL`：窗口前半段与后半段方向相反
- `INSUFFICIENT_HISTORY`：可用期数不足

阈值在 `config/methodology.yaml` 中配置，全部规则化，无 LLM。

## 5. Data Quality

系统暴露：stale filing、failed ingestion、unresolved CUSIP、amendment pending、
duplicate filing、malformed filing、incomplete quarter、missing historical
comparison。UI 总览页必须展示 Data Quality Status；数据缺失时页面不得假装正常。
