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

## 金额单位（2026-09-07 正确性修复）

- `holdings.value` 保留 SEC 原始填报整数，不把原始值改写成美元。
- `effective_positions.value` 与 `effective_periods.total_value` 统一为 USD。
- 金额口径身份为 `USD_SEC_FILING_DATE_2023_01_03_V1`，作为有效状态的版本身份组成部分；
  不改变机构评分档位。每个来源的 `filing_date`、口径身份写入 provenance，原始 checksum 与日期写入状态 hash。
- 依据每份 filing 实际提交日，而非报告季度：2023-01-03 之前的原始千美元数乘 1000，
  当日及以后的美元数乘 1；历史季度的晚到修订也按其提交日单独处理。
- 日期缺失/无效、原始 manifest 与 DB 日期冲突、乘法/汇总整数溢出均不允许形成可发布数据。
- 独立 Gate 2 从原始 manifest 日期重新换算，不调用生产换算函数；Gate 1 仍对账原始值。
- 旧派生表不能直接复用。须从来源重新生成有效状态并重跑真实 Gate；旧验收不适用于这个新口径身份。
- 这只是 SEC 格式单位转换，不根据数量/价格猜测或“纠正”申报人的填报错误。

依据：[SEC Form 13F FAQ，Question 36 与 62](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f)。

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
# Source quarantine / 源异常隔离（0.1.1）

复用 schema v3，不迁移或覆盖旧数据库：filings 的 ingest_status 新增可读状态
`QUARANTINED`；同 manager_id / report_period 全部申报同步隔离。
holdings 保留原始行及 provenance，portfolio_weight 为 NULL；effective_periods 为
`INCOMPLETE`、total_value 为 NULL，无 effective_positions 或 components。
quality_events 的 `SOURCE_QUARANTINED` / ERROR 记录精确策略 ID、策略 SHA-256、方法版本、
源文双 SHA-256 与原始控制数。隔离是持久化状态，重新分析或改方法学版本不会自动恢复。
