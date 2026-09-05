# Data Model — 数据模型 (schema v3)

SQLite（`data/thirteenf.db`，gitignored，可从 `data/raw` 重建）。

## 表

| 表 | 用途 | 关键字段 / 约束 |
|---|---|---|
| `schema_version` | 迁移版本 | version PK |
| `managers` | 机构主数据 | cik UNIQUE；scoring_status、signal_quality |
| `filings` | filing 元数据与 amendment 审计链 | accession UNIQUE；amendment_number/type/status；amends_filing_id；cover/raw checksum/path |
| `holdings` | SEC 原始 information-table 行 | UNIQUE(filing_id, row_ordinal)；put_call 与 SH/PRN 原样保留 |
| `securities` | 证券主数据 | cusip UNIQUE；mapping_status/source/date |
| `mapping_history` | 映射审计 | security_id；effective_date |
| `effective_periods` | 某 manager/quarter/version 的有效状态 | READY / AMENDMENT_PENDING / INCOMPLETE；state_hash |
| `effective_filing_components` | 有效状态由哪些 filing 组成 | BASE 或 SUPPLEMENT；确定性 sequence |
| `effective_positions` | 按经济头寸键聚合后的分析输入 | UNIQUE(period, security, put_call, shares_type)；provenance_json |
| `position_changes` | 变化分析 | UNIQUE(manager, security, put_call, shares_type, period, version) |
| `consensus_scores` | 加权共识 | raw_contributions JSON；键含 put_call 与 shares_type |
| `trends` | 趋势 | 键含 put_call、shares_type、horizon 与 methodology version |
| `quality_events` | 数据质量事件 | event_type/severity/message |

## 主键与唯一约束

- CUSIP 是 canonical security identity；ticker 仅为派生展示字段，可 NULL。
- `holdings` 用 `(filing_id, row_ordinal)` 保留原始行序；同 CUSIP 多行不得覆盖。
- raw row 同时保存 `ssh_prnamt_type`、`investment_discretion`、`other_manager`。
- 有效经济头寸键为 `(effective_period_id, security_id, put_call, shares_type)`。
- PUT、CALL、普通头寸以及 SH、PRN 永不错误合并。
- `effective_positions.provenance_json` 必须列出聚合所用的每个 `(filing_id, row_ordinal)`。
- `13F-HR/A` 缺少可靠 cover metadata 时标记 `AMENDMENT_PENDING`，不生成正常分析。

## Amendment 状态

- `RESTATEMENT`：成为新的 BASE，并重置此前 supplement。
- `ADD_NEW_HOLDINGS`：作为 SUPPLEMENT 叠加在当前 BASE 上。
- migration 不猜 amendment 类型；旧库中的 amendment 默认进入 `AMENDMENT_PENDING`。
- v2 → v3 会保留 managers、filings、holdings 和 security master；旧版派生分析表会清空并从原始证据重算，因为旧键缺少 `shares_type` 且旧 amendment 选择规则不可靠。

## 关键索引

- filings(manager_id, report_period)
- holdings(manager_id, report_period)、holdings(cusip)、holdings(filing_id)
- position_changes(manager_id, security_id)、position_changes(report_period)
- securities(cusip)、securities(ticker)
- effective_periods(manager_id, report_period)
- effective_positions(security_id, report_period)、effective_positions(manager_id, report_period)

## 只读 UI

Streamlit/public UI 使用 `connect_readonly(..., immutable=True)` 打开发布快照；ingestion 和 rebuild 才使用可写连接。这样公开页面无法通过查询路径修改数据库。

## 重建

```powershell
python -m thirteenf rebuild
```

同样的 raw 数据 + 同样的 methodology_version ⇒ 相同分析结果（确定性复现）。
