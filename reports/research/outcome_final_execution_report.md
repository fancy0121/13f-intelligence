# 13F Institutional Intelligence System
# Outcome Validation v0.2 — Final Execution Report

> Generated: 2026-08-24
> Mode: AUTONOMOUS OBJECTIVE EXECUTION（目标文件完整读取，无截断）

## Repository

- Baseline SHA: `86b4d0696b6135fd909027d63366b839075deee2`
- **Outcome Protocol Freeze SHA**: `56b3404115aa00ebad739070b61d841890751412`
- Final SHA: `03ca1bc`（本报告提交后以 `git log` 为准）
- Commits:
  - `56b3404` outcome protocol freeze
  - `03ca1bc` provider audit + outcome adapter framework + audits + frozen ideas
  - `(pending)` final execution report
- Git status: clean

## Provider

- Selected provider: **NO_APPROVED_PROVIDER**
- Yahoo Finance chart API passed price gates (adjusted close, 4:1 split event,
  ^GSPC benchmark, 404 for unknown/delisted) but **failed symbol identity**:
  CUSIP search returns foreign listings (GOOGL→1GOOGL.MI, TSMC→0LCV.IL) and
  symbol-history issues (Block SQ→XYZ).
- OpenFIGI anonymous mapping does not support CUSIP/ISIN; Stooq blocked.
- Licensing: Yahoo endpoints unofficial; research-only use, no redistribution.
- Retrieval coverage: not applicable (no approved provider).

## Data

- Eligible observations: A0 75,385 (dev) / A1_2Q 23,536 / A1_3Q 7,381
  (from frozen v0.1 manifests)
- Outcome-resolved: **0**（无 approved provider / curated symbol map 为空）
- Unresolved: all eligible observations（`OUTCOME_UNRESOLVED_SECURITY`）
- 3M/6M/12M sample counts: 0（NOT_EVALUATED）

## Experiments

O0 / O1 / O2：**NOT_EVALUATED_NO_APPROVED_PROVIDER**（protocol §4/§8）。

## Holdouts

- 原 manifests 复用（time/manager/security/combined），未 rehash。
- Outcome-resolved subset: empty；dropped observations: none（无样本）。

## Null Model

- 方法：security×quarter 组内 label permutation；seed 固定
  `NULL_SEED="13f-outcome-v0.2-null"`；repetitions=200（预注册）。
- 状态：`NULL_MODEL_EXECUTION=NOT_EXECUTED_NO_APPROVED_PROVIDER`
  （框架与测试已交付，无 outcome 数据可运行）。

## Economic Outcomes

无（未伪造）。所有 metrics 无值。

## Coverage

- O1 coverage cost vs O0（结构性）：−69% eligible；O2 −90%（来自 v0.1）。
- Outcome coverage：N/A（无样本）。

## Concentration

- Manager / security / time-regime outcome audits：NOT_EVALUATED。
- v0.1 leave-one-manager-out flip fraction 均已低（无 MANAGER_DOMINATED）。

## Leakage

- 框架层审计完成（outcome_leakage_audit.md）：无严重泄漏；正式 evaluation
  未执行（无 approved provider），因此无运行期泄漏风险。

## Falsification

- O1 falsification criteria：预注册；未触发（未执行）。
- O2 falsification criteria：预注册；默认不选 O2（无证据）。

## Simplest Surviving Model

`A0_ONLY`

## What We Should Not Build

见 `docs/rejected_or_frozen_ideas.md`（FROZEN_UNLESS_NEW_EVIDENCE）：
精确 manager score、0–100 consensus headline、A2 weight-direction signal、
strategy clustering、ML ranking、LLM signal、portfolio-specific tuning。

## Product Candidate

`PRODUCT_CANDIDATE_STATUS=NO_CANDIDATE`

## Gates

- Outcome Protocol Integrity: **PASS**（freeze commit 可证明）
- Provider Quality: **FAIL → NO_APPROVED_PROVIDER**（symbol identity 不达标；
  按 protocol 走 NOT_EVALUATED，不伪造）
- Leakage: **PASS**（框架审计）
- Reproducibility: **PASS**（adapter 测试确定性；无 outcome 运行）
- Mapping Bias: **N/A→NOT_APPLICABLE**（无 resolved sample；框架已预注册）
- Null Comparison: **NOT_EXECUTED**（框架已交付）
- Holdout Robustness: **N/A**（无 outcome 样本）
- Concentration: **N/A**（无 outcome 样本）
- Simplicity: **PASS**（A0_ONLY）
- Real-World Decision Utility: **PENDING**

## Known Weaknesses

- 无 approved market data provider ⇒ 无法回答“经济意义”问题（本阶段核心
  问题未获实证）。
- CUSIP→symbol 是阻塞项：需要 curated、来源标注、share-class/ADR/symbol-
  history aware 的映射文件后才能解锁。
- Yahoo 为 research-only 非官方端点，需接受许可风险或另寻 provider。

## Next Step

1. 人工/可信源构建 `config/outcome_symbols.csv`（CUSIP→symbol，带
   provenance/effective_date/share class/ADR 标注）；
2. 提供后重跑 `outcomes` adapter（框架已就绪）；
3. 若 mapping 覆盖 ≥ 阈值且经审计，再执行 O0/O1/O2 正式 outcome
   evaluation + null + holdout；
4. 未达标前保持 `A0_ONLY` / `NO_CANDIDATE`。

## Final Status

```
OUTCOME_VALIDATION_STATUS=PARTIAL_NO_APPROVED_MARKET_DATA
PRODUCT_METHODOLOGY_STATUS=NO_RULE_APPROVED
PRODUCT_CANDIDATE_STATUS=NO_CANDIDATE
FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER
REAL_WORLD_DECISION_UTILITY=PENDING
```

