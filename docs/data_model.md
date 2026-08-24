# Data Model — 数据模型 (v0.1)

SQLite（`data/thirteenf.db`，gitignored，可从 `data/raw` 重建）。

## 表

| 表 | 用途 | 关键字段 / 约束 |
|---|---|---|
| `schema_version` | 迁移版本 | version PK |
| `managers` | 机构主数据 | cik UNIQUE；scoring_status、signal_quality |
| `filings` | filing 元数据 | accession UNIQUE；is_amendment；raw_checksum；raw_path |
| `holdings` | 解析后的持仓 | UNIQUE(filing_id, row_ordinal)；put_call 分离 |
| `securities` | 证券主数据 | cusip UNIQUE；mapping_status/source/date |
| `mapping_history` | 映射审计 | security_id；effective_date |
| `position_changes` | 变化分析 | UNIQUE(manager, security, put_call, period, version) |
| `consensus_scores` | 加权共识 | raw_contributions JSON；UNIQUE(security, put_call, period, version) |
| `trends` | 趋势 | UNIQUE(security, put_call, period, horizon, version) |
| `quality_events` | 数据质量事件 | event_type/severity/message |

## 主键与唯一约束

- CUSIP 是 canonical security identity；ticker 仅为派生展示字段，可 NULL。
- holdings 用 `(filing_id, row_ordinal)` 保留原始行序，防止同 CUSIP 多行丢失。
- 分析键一律含 `put_call`：PUT / CALL 与普通股永不合并。

## 关键索引

- filings(manager_id, report_period)
- holdings(manager_id, report_period)、holdings(cusip)、holdings(filing_id)
- position_changes(manager_id, security_id)、position_changes(report_period)
- securities(cusip)、securities(ticker)

## 重建

```powershell
python -m thirteenf rebuild
```

同样的 raw 数据 + 同样的 methodology_version ⇒ 相同分析结果（确定性复现）。
