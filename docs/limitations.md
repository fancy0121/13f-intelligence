# Limitations — 13F 系统限制 (v0.1)

以下限制必须被系统、UI 与文档持续承认：

## 1. 45 天披露延迟

13F 在季度结束后最多 45 天才提交；系统数据天然滞后，最新季度可能不完整。
`Data Quality Status` 会显示 stale / incomplete quarter。

## 2. Short positions 不披露

13F 只披露多头。`reported long exposure increased` 不能解释为
`manager is bullish`——空头、对冲与衍生品不可见。

## 3. Derivatives incomplete

PUT/CALL 只以期权形式披露，其他衍生品（swaps、futures、forwards）不完整或缺失。

## 4. Confidential treatment

部分持仓可能申请保密（confidential treatment）而延迟披露。"当季未披露"不能被
绝对解释为"不持有"；系统对后续 amendment 披露历史持仓具备重算能力。

## 5. Amendments

13F-HR/A 可能修正原 filing。系统以有效版本重算分析，原始版本永久保留；
不会不可逆静默覆盖。

## 6. No exact trade timing

13F 只给季度末快照，无法得知精确买入/卖出时间。

## 7. No exact cost basis

无法从 13F 得知真实成交价格与成本。任何价格上下文只能表述为
`estimated acquisition context`，禁止写成 `manager purchase price`。

## 8. 13F ≠ investment thesis

13F 是持仓行为的有限证据，不是完整投资观点。系统只输出
`EVIDENCE_STRENGTHENS / EVIDENCE_WEAKENS / NO_MEANINGFUL_CHANGE /
INSUFFICIENT_EVIDENCE`，不产生投资建议。
