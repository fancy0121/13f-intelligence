# Outcome Validation v0.2 — Protocol (PRE-REGISTERED)

> 本文档在正式 outcome evaluation 之前冻结。冻结后不得因结果修改。
> 方法论变更只能进入 NEXT_EXPERIMENT_VERSION。

## 0. Purpose

回答唯一核心问题：

> A0、A1_2Q、A1_3Q 这些已冻结的结构性信号，在其 13F 信息真正公开之后，
> 是否对应任何稳定、样本外、具有经济意义的 forward outcome 差异？

不是回答“哪个模型赚最多钱”，也不是优化参数。

## 1. Frozen Prior Conclusions (not modifiable)

- A0: KEEP
- A1_2Q: WEAKLY_SUPPORTED
- A1_3Q: EXPERIMENT_AGAIN
- A2/A3: NO_INCREMENTAL_VALUE / INSUFFICIENT_EVIDENCE
- A4: NOT_EXECUTED
- PRODUCT_METHODOLOGY_STATUS=NO_RULE_APPROVED
- REAL_WORLD_DECISION_UTILITY=PENDING

## 2. Experiment Scope (strict)

仅主实验：

- O0 = A0 baseline (net_directional)
- O1 = A1_2Q persistence
- O2 = A1_3Q persistence

禁止新增 2.5Q/4Q persistence、新 weights、新 threshold、新 filters、
新 portfolio-weight score、新 consensus formula。新想法只记录为
`NEXT_EXPERIMENT_CANDIDATE`。

## 3. Information Available Date (hard constraint)

- 每条 observation 的起点 = effective filing 的 `filing_date`
  （13F-HR/A 按 amendment publication date）。
- 禁止使用 `report_period` / quarter_end 作为市场可知时间。
- 2026-06-30 holdings 于 2026-08-14 filing ⇒ information date = 2026-08-14。
- 未来信息不得提前进入 outcome window。

## 4. Provider Policy & Acceptance Gate

候选 provider 必须：

- 免费、可程序化、可重复、历史覆盖充足
- corporate-action 处理清楚（split / dividend / adjusted close）
- 无需付费凭证
- symbol identity 可审计（US listing 优先、share-class aware、ADR aware、
  conflict aware）

验收必须验证：

- historical daily prices
- adjusted close 或 total-return-compatible series
- split handling（fixture）
- dividend handling 或明确不含
- symbol identity resolution
- delisted / stale 缺失状态
- benchmark series（S&P 500 代理）

若 provider 不通过：**不得 BLOCK**；输出
`FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER`，完成
provider audit + outcome adapter framework + tests + future-ready protocol，
不伪造 outcome。

## 5. Security Identity / Price Mapping

- 底层 identity：security_id / CUSIP（FACT layer canonical）。
- 行情 symbol 仅是 outcome-enrichment key。
- CUSIP→symbol 映射必须：provenance、effective date、share-class aware、
  ADR aware、conflict aware。
- 无法可靠映射 ⇒ `OUTCOME_UNRESOLVED_SECURITY`。禁止猜测。
- 允许 curated mapping 文件（人工/来源标注）；无 curated 行时不推断。

## 6. Mapping Bias Policy

必须报告：

- total eligible observations
- price-resolved observations
- unresolved observations
- resolution rate by manager / security size proxy / experiment variant

若 outcome sample 明显偏向热门证券：
`OUTCOME_MAPPING_SELECTION_BIAS`，并在结论降级。

## 7. Outcome Horizons

固定：

- 3M / 6M / 12M（交易日 horizon）

从 information_available_date 后**第一个可交易日**开始，按固定交易日数计算。
冻结后不得更换。

## 8. Primary Outcome Metrics

每个 variant × horizon × split 至少：

- Absolute return（3M/6M/12M）
- Benchmark excess return（相对 primary benchmark）
- Hit rate（excess > 0）
- Median（必须报告，不只 mean）
- Dispersion（std / percentile）
- Downside（negative excess rate、lower-tail）

## 9. Primary Benchmark

- S&P 500 broad-market total-return-compatible proxy（如 Yahoo `^GSPC`，
  需在 provider audit 中说明 adjustment semantics）。

## 10. Secondary Benchmark

- Sector benchmark：仅 secondary；数据不完整 ⇒ `SECTOR_BENCHMARK_PARTIAL`；
  不猜 sector；不得阻塞主实验。

## 11. 禁止复杂 Factor Model

禁止 Fama-French、factor-neutral alpha、multi-factor regression、ML alpha、
risk-model residualization。列入 Future Research。

## 12. Directional Interpretation

- 沿用冻结的 A0/A1 分类：positive = NEW/ADD（或 persistence+），negative =
  REDUCE/EXIT，neutral = UNCHANGED / insufficient。
- 不因 forward return 结果改变分类。
- O0/O1/O2 不是 BUY/SELL。

## 13. Randomized Null Baseline

- 保留样本结构（quarter distribution、observation count、security frequency）。
- 固定 `NULL_SEED`；固定随机化方案（permute signal labels within
  security×quarter groups）。
- 预注册 repetition count（=200）与比较规则：
  - 若 variant 的 excess-return median 超过 null 分布 95th percentile，
    记 `EXCEEDS_NULL_P95`；
  - 若仅 dev 超过、holdout 不超 ⇒ 不成立。
- 不得运行多种 null 后挑最有利。

## 14. Holdout Integrity

继承上一阶段 manifests（time/manager/security/combined），**不重新 hash**。
outcome-resolved 子集必须记录：

- original holdout membership
- outcome-resolved subset
- dropped observations + reason

## 15. Evaluation Grid

O0/O1/O2 × {dev, time, manager, security, combined} × {3M,6M,12M}，
每个 cell 报告 metrics。样本不足 ⇒ `INSUFFICIENT_SAMPLE`。

## 16. Complexity Comparison

- O1 vs O0：是否提高 economic outcome / excess consistency / 降低 downside，
  还是仅 coverage 下降筛掉 noisy samples？
- O2 vs O1：3Q 是否真正提高经济信息，还是 selection-by-persistence？

## 17. Coverage Penalty

结论必须同时显示 quality 与 coverage。O2 若只覆盖 10% 样本，必须展示
coverage tradeoff。

## 18. Statistical Discipline

- 不把 p<0.05 当产品批准条件。
- 只测预注册组合（3 variants × 3 horizons × 5 splits × predefined metrics）。
- 任何额外 exploratory ⇒ `EXPLORATORY_ONLY`，不与预注册结果混用。

## 19. Concentration Audits

- Manager：leave-one-manager-out outcome sensitivity ⇒
  `ECONOMIC_RESULT_MANAGER_DOMINATED`
- Security：top-N contribution；leave-top-N sensitivity；少数大科技股驱动
  ⇒ 降级结论。
- Time regime：仅描述性；仅少数季度有效 ⇒ `TIME_REGIME_SENSITIVE`

## 20. Falsification Criteria (pre-registered)

### O1 falsified if ANY:

1. holdout excess outcome 与 O0 无实质差异（median |diff| < 1%）
2. combined holdout 方向反转
3. null comparison 无优势
4. result dominated by few managers/securities
5. coverage cost 过大（resolved eligible < 20% of O0）
6. downside 未改善
7. 预注册 sensitivity 下效果消失

### O2 falsified if:

- 相对 O1 无明确经济增量（median excess diff < 1% 或 downside 不改善），
  默认选择 O1 或 O0。

## 21. Success / Failure Criteria

- `CANDIDATE_FOR_PRODUCT_APPROVAL`：无严重 leakage、样本外方向不反转、
  各 holdout 不崩、非单一 manager/security 主导、相对 O0 有清晰增量、
  magnitude 有实际意义、coverage tradeoff 可接受、相对 null 有优势、
  符合 simplest-surviving-model。
- 否则：REJECT / EXPERIMENT_AGAIN / INSUFFICIENT_EVIDENCE。
- 若无任何复杂规则证明增量 ⇒ `A0_ONLY`（完全允许，是成功结果）。

## 22. Provider Decision (frozen at protocol write)

基于本 protocol 编写时的 Provider Audit：

- Yahoo chart API：价格能力通过（adjusted close、splits/dividends、
  ^GSPC、404 for unknown/delisted）。
- CUSIP→symbol resolution：**FAIL**（CUSIP 搜索返回外国上市/历史符号，
  如 GOOGL→1GOOGL.MI、TSMC→0LCV.IL；symbol-history 如 SQ→XYZ 无法可靠
  处理；OpenFIGI 匿名不支持 CUSIP/ISIN）。
- 结论：**NO_APPROVED_PROVIDER**（symbol identity 项不达标）。

因此正式 outcome evaluation 状态：

`FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER`

本阶段交付：provider audit、outcome adapter framework、tests、
future-ready protocol、mapping coverage 报告。**不伪造 outcome**。

## 23. Fixed Seeds

```text
NULL_SEED = "13f-outcome-v0.2-null"
```

## 24. Deliverables

- `research/outcome_protocol_v0.2.md`（本文档）
- `reports/research/market_data_provider_audit.md`
- `reports/research/outcome_mapping_coverage.md`
- `reports/research/outcome_leakage_audit.md`
- `reports/research/outcome_validation_results.md`
- `reports/research/null_model_results.md`
- `reports/research/outcome_concentration_audit.md`
- `reports/research/outcome_holdout_results.md`
- `reports/research/outcome_final_recommendation.md`
- `docs/rejected_or_frozen_ideas.md`
- machine-readable artifacts
- `FINAL_OUTCOME_RESEARCH_MANIFEST`

## 25. Final Status Semantics

- `OUTCOME_VALIDATION_STATUS=PARTIAL_NO_APPROVED_MARKET_DATA`
  （protocol/adapter/tests/audits 完整，但无 approved market data）
- `PRODUCT_METHODOLOGY_STATUS=NO_RULE_APPROVED`（不变）
- `REAL_WORLD_DECISION_UTILITY=PENDING`（不变）

---

OUTCOME_PROTOCOL_FREEZE_VERSION=v0.2
