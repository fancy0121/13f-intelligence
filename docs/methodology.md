# Methodology — 13F 分析方法论 (v0.1)

> 中文解释 + 英文标准术语。本文档由 `config/methodology.yaml` 中的
> `methodology_version` 治理；任何规则变更必须 bump version、重算、重测。

## 1. 13F 的含义

Form 13F（13F-HR / 13F-HR/A）是 SEC 要求的机构季度持仓披露。它只包含：

- 报告期的多头、可辨识证券仓位（common stock、options 的 PUT/CALL 等）；
- 每只证券的 CUSIP、issuer、title of class、value、shares。

原始 `value` 按该 filing 的 SEC 填报单位保存；分析层统一换算为 USD，
特别处理 2023-01-03 格式切换及晚到历史修订，详见 [金额单位](data_model.md)。
本轮修复恢复原定美元语义，不新增评分规则；金额口径身份与运行代码 hash 共同区分旧错误结果，必须重建、重验。

它**不包含**：空头、大部分衍生品、完整基金组合、精确成交时间、精确成本、投资论点。

## 2. Position Change Rules

对每个 `(manager, security, put_call, shares_type, report_period)` 与**相邻、完整、
READY 的上一季度**比较，不能跨缺季。首次出现于数据库不等于新建仓；
首季或缺少比较季时不生成变化记录，标记 `MISSING_HISTORICAL_COMPARISON`。

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
- `portfolio_weight = value / sum(value)`（分析层 denominator 为该机构当季
  effective state 全部披露仓位，含相互区分的 SH/PRN、PUT/CALL；不是完整基金 NAV。
  原始 holdings 表的单 filing 权重只用于原始层审计，不作为跨季分析权重）
- `weight_change = weight_now - weight_prev`

**Shares 与 Weight 分离**：shares 增加但 portfolio weight 下降时，change_type 仍为
ADD，但 `weight_change < 0` 被保留展示，禁止解释为 conviction strengthening。

**Amendment 语义**：不能将所有 13F-HR/A 直接覆盖原报告。
`RESTATEMENT` 重述有效状态；`NEW HOLDINGS` 按封面语义补充披露。
按 SEC accepted_at 与 accession 确定回放顺序，原始文件及版本保留。
类型缺失、封面不一致或来源不全则阻止有效状态晋级。更正后重算相关季度及后续比较。
后续补披露不表示历史上原本未持有；本系统只比较已公开的报告多头暴露。

**原始格式与异常边界**：SEC 的 `xslForm13F_Xnn/` 是展示路径，采集使用同一
accession 的原始 XML。目录漏列附件时，只按该 accession 完整申报文本中的明确
`INFORMATION TABLE` 文件名寻找附件，并同时保存定位用完整文本，禁止猜文件名。
普通 `13F-HR` 封面可以省略 `isAmendment` 元素：SEC v1.9 schema 的 `COVER_PAGE`
将其声明为 `minOccurs="0"`。只有明确为 HR 且无修订元数据时才视为普通申报；
空值、冲突标记或 HR/A 的缺失标记仍拒绝。依据：[SEC XML 官方规范](https://www.sec.gov/file/edgar-form-13f-xml-technical-specification-1-9)。
真实回归样本：`tests/fixtures/baupost_2026q2_primary_doc.xml`，来自
[Baupost 0001061768-26-000010](https://www.sec.gov/Archives/edgar/data/1061768/000106176826000010/primary_doc.xml)。

Submissions 的必需对象、数组、列对齐和重复 accession 元数据均须验证；原响应按
checksum 保存。发现清单记录查询窗口、已取/跳过的历史分片及预期 accession，并与
最终双组件 manifest 对照。`discovery COMPLETE` 只表示申报发现完成，不表示历史12Q齐全，
更不表示分析通过；来源清单的语义身份参与 Gate 指纹。

封面与信息表的行数或金额合计不一致时，默认严格阻止新分析库生成。
唯一已批准例外是本文末尾 v0.1.1 的精确异常隔离政策：原值保留、整个机构季度退出分析，
不是接受矛盾数字；必须显式传入政策文件，不能自动应用于新异常。
**不能因为差额小就自动解释为四舍五入，不能修补原值或悄悄扩大容差。**
异常隔离、容差或替代申报主体拼接均需显式治理批准，再重算和重验。

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

**当前限制**：默认 `min_prev_now` 下，NEW/EXIT 的缺失端权重会使 significance 为零，
不计入分数，NEW-only/EXIT-only 因而没有共识分数。它们仍在客观变化表中显示。
这不是“中性结论”，不得补零代替。若要改变这条经济解释规则，须审批方法学新版本，
不应作为 UI 修复顺手变更。当前治理配置没有批准机构，不制造默认评分。
评分文件版本必须与计算版本一致，移出批准集合的机构立即失去批准状态。

申报主体身份核验不是策略独立性证明。当前 UI 的“已核验申报主体”只表示 CIK/scope
核验；内部历史字段名中出现 independent 也不构成策略独立性。按策略标签计数亦不能
作为相关性模型或独立验证票数。

## 4. Trend

在 consensus 序列上按 1Q / 4Q / 8Q 窗口计算：

- `STRENGTHENING`：窗口均值 > 阈值
- `WEAKENING`：窗口均值 < -阈值
- `STABLE`：|均值| ≤ 阈值
- `REVERSAL`：窗口前半段与后半段方向相反
- `INSUFFICIENT_HISTORY`：可用期数不足、季度不连续，或该证券缺少当前季度分数。
  四条分散的历史记录不是连续 4Q；旧季度的趋势不能被显示成当前趋势。

阈值在 `config/methodology.yaml` 中配置，全部规则化，无 LLM。

## 5. Data Quality

系统暴露：stale filing、failed ingestion、unresolved CUSIP、amendment pending、
duplicate filing、malformed filing、incomplete quarter、missing historical
comparison。UI 总览页必须展示 Data Quality Status；数据缺失时页面不得假装正常。

## 7. 2026-09-07 正确性修复与再验收

本次修正的是违反上述既有规则的实现（首季伪 NEW、跨缺季趋势等），未批准新主观评分。
旧报告不能继承为新代码的通过证明：Gate 身份现在同时绑定源码、运行配置、证券解释表、
raw、effective state 与 DB checksum，必须对新版本重新验收。
下载/解析成功不等于可发布；真实人工 Gate 2 不能由自动测试或合成 reviewer 代签。
空 INFORMATION TABLE 当前保守隔离待人工复核，不把它推断成清仓。
封面包含 tableEntryTotal/tableValueTotal 时，必须与原始表逐项数量及金额汇总一致。

## 6. Manager Scope（v0.1.1）

同一品牌可能对应多个 SEC filing entity。系统采用 `VERIFIED_WITH_SCOPE` 状态：

- 明确声明追踪的 filing entity（见 `docs/manager_scope.md`）；
- 平行实体（如 PERSHING SQUARE INC vs PSCM L.P.）不合并；
- 历史实体（如 2016 年前的 APPALOOSA MANAGEMENT LP）不混入当前持仓；
- ticker 或名称相似不构成合并依据；CUSIP 仍是 canonical identity。
# 0.1.1 — Approved source quarantine / 已批准的源异常隔离

2026-09-10：Owner 已批准隔离已核实的 16 份 SEC 原文内部矛盾，而不是修补数字。
精确清单在 `config/source_quarantine.json`，从
`reports/validation/correctness-foundation-2026-09-07/source-anomalies.csv` 提取。
每项绑定 CIK、accession、报告季度、cover / information table 两个 SHA-256，
以及原文声明和实际逐行求和的控制数。不存在金额容差；1 美元或 1 原始单位差异也不忽略。

- 显式传入此策略才能重建；未匹配、字节变化、控制数变化或版本不符均 FAIL。
- `filings.ingest_status=QUARANTINED` 覆盖整个 manager-period 的所有申报，
  包括同季度看似正常的 amendment。原始 holdings 的 shares/value 不变，权重为 NULL。
- 对应 effective period 保留为 `INCOMPLETE`，质量事件为 `SOURCE_QUARANTINED`，
  不生成 effective positions、filing components、当季变化或跨隔离季度比较。
- 这表示 **不知道这一季度的可靠组合**，绝不表示持仓为零、EXIT 或无变化。
- 后续 amendment 不会自动解除隔离；需要针对新证据重新审批并重建。
- 剩余 READY 数据可做独立数据/分析核验；隔离覆盖率必须单列，不缩小原始机构分母。
  Gate 2 人工复核、Gate 3 现实价值验证及正式发布许可仍分别独立，隔离批准不等于发布批准。
- 评分文件仅对齐方法学版本，未批准任何机构评分，未改评分档位或权重。
