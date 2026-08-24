# AGENTS.md — 13F Institutional Intelligence System

本仓库默认由 AI Agent / Codex 参与协作。
先读文件，再动手；先验证，再汇报。

## 项目宪法（不可改）

1. **Source of Truth**: 唯一权威源是 SEC EDGAR。不得用第三方数据库或 LLM 替代。
2. **Deterministic First**: holdings / shares / value / portfolio weight / change type /
   consensus / trend 全部由确定性代码计算。LLM 不得写入关键数字、决定分类、猜 CUSIP
   映射或修补 SEC 数据。
3. **No Hallucinated Mapping**: CUSIP → ticker 无法可靠确认时 `ticker = NULL`，进入
   unresolved workflow。禁止 issuer fuzzy guess、LLM guess 或静默 fallback。
4. **13F Interpretation**: 13F 不披露空头、衍生品、成本、精确时机与完整组合。任何措辞
   不得把 "reported long exposure increased" 写成 "manager is bullish"。
5. **No Automatic Trading**: 只有 evidence strengthens / weakens / neutral / insufficient。

## 分析分层

- **Objective Layer**: 纯 SEC 确定性事实（holdings、NEW/ADD/REDUCE/EXIT、share change、
  portfolio weight）。所有 manager 均可参与。
- **Governed Interpretation Layer**: 仅 `scoring_status = APPROVED` 的 manager 可进入
  Weighted Consensus、high-quality manager count 与 governed interpretation。
  未批准 manager：`signal_quality = NULL`，`scoring_status = NOT_APPROVED`。
  禁止默认中性评分（如 0.5）。

## 语言

- UI：中文
- Python identifiers / database schema / tests / logs：英文
- methodology 文档：中文解释 + 英文标准术语

## 执行纪律

- 每阶段先测试，后 checkpoint commit；保持小 diff。
- 不加入 mock data 冒充真实结果；不降低 Gate；不静默吞掉数据错误。
- 任何 Gate FAIL：停止向下一阶段推进，修复并重新验证。
- 不把 raw 大型数据提交进 Git；不提交 secrets。

