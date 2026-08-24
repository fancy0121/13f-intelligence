# Methodology (v0.1 draft)

> 中文解释 + 英文标准术语。本文档由 `config/methodology.yaml` 中的
> `methodology_version` 治理；规则变更必须 bump version 并重算、重测。

## 13F 的含义

13F 是 SEC 要求的机构季度持仓披露（Form 13F-HR / 13F-HR/A），只披露多头、可辨识证券
仓位；不含空头、衍生品、成本与精确交易时机。

## Position Change Rules

- NEW / ADD / REDUCE / EXIT / UNCHANGED（详见代码 `src/thirteenf/changes.py`）。

## Portfolio Weight

- `value / sum(value)`，denominator 为该 filing 全部披露行。

## Consensus

- 仅 APPROVED manager 参与（Governed Interpretation Layer）。

## Trend

- 1Q / 4Q / 8Q 规则化标签。

（Phase 8 将补全正式版本。）

