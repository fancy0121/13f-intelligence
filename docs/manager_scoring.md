# Manager Scoring (v0.1 draft)

> 治理约束：禁止默认中性评分。未批准 manager 必须 `signal_quality = NULL` 且
> `scoring_status = NOT_APPROVED`，不得进入 Weighted Consensus / high-quality count。

## 分层

- Objective Layer：所有 manager 可参与（纯 SEC 事实）。
- Governed Interpretation Layer：仅 APPROVED manager。

## v0.1 粗粒度分层（目标）

- HIGH / MEDIUM / LOW / NON_SIGNAL

（Phase 4 将实现机制；Phase 8 补全治理文档。）

