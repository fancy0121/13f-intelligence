# Rejected or Frozen Ideas (governance freeze)

> Updated: 2026-08-24

以下想法状态为 `FROZEN_UNLESS_NEW_EVIDENCE`：未经新证据不得重新引入。

| Idea | Status | Reason |
|---|---|---|
| Precise manager skill score (e.g. 0.873) | FROZEN | No evidence; A3 NO_INCREMENTAL_VALUE |
| 0–100 normalized consensus headline | FROZEN | False precision; not supported |
| A2 portfolio-weight-direction aggregate signal | FROZEN | NO_INCREMENTAL_VALUE vs A0 |
| Strategy clustering / ML manager ranking | FROZEN | Over-engineered; no evidence |
| LLM-generated signal | FROZEN | Deterministic-first constitution |
| Portfolio-specific methodology tuning | FROZEN | Portfolio overfitting prohibited |

这不是永久禁止研究，而是禁止无证据重新引入。

## v0.2.1 Addendum (2026-08-24) — new negative evidence

Security Resolution Validation & Frozen Outcome Unlock:

| Idea | Status | Reason |
|---|---|---|
| `NO_APPROVED_PROVIDER` blanket verdict | RETRACTED | OpenFIGI supports CUSIP (ID_CUSIP/ID_CUSIP_8_CHR/ID_ISIN); price provider (Yahoo) approved separately |
| Outcome Unlock under current rules | FROZEN (blocked) | R5 coverage FAIL (O0 69.99% < 90%) + R6 bias FAIL (differential >5pp, VARIANT_MAPPING_BIAS) |
| Lower coverage thresholds to "make it run" | REJECTED | Protocol freeze; correctness > convenience |
| OpenFIGI-only fund verification (no SEC corroboration) | NEXT_PROTOCOL_CANDIDATE | Not allowed in v0.2.1; needs external approval as new protocol |
| Curated Tier-4 fund table for top funds | NEXT_PROTOCOL_CANDIDATE | Would recover only part of ~25% fund observations |

## v0.2.2 Addendum (2026-08-24) — semantic audit governance

Security Semantic Audit (outcome-blind):

| Idea | Status | Reason |
|---|---|---|
| Operating-Equity-only research universe (v0.3) | NEXT_PROTOCOL_CANDIDATE | JUSTIFIED_FOR_NEW_PREREGISTRATION (J1-J5), but must be a fresh external-approved preregistration; NOT started |
| Excluding pooled vehicles to improve coverage | REJECTED | Hypothesis-specification overfitting; classification must be semantic, not convenience |
| Using higher operating resolution as justification alone | REJECTED | Coverage is technical convenience, not economic semantics (J3) |
| Re-running broad O0/O1/O2 with new denominator | REJECTED | v0.2.1 conclusion preserved |
| Predictive-signal search beyond frozen tests (4Q/5Q persistence, manager scores, ML) | FROZEN | Research Stop Rule (docs/research_stop_rule.md) |

## v0.3 Addendum (2026-08-26) — operating equity outcome validation

Operating Equity 13F Evidence Hypothesis (NEW_HYPOTHESIS_AFTER_OUTCOME_BLIND_
SEMANTIC_AUDIT):

| Idea | Status | Reason |
|---|---|---|
| O1_2Q persistence incremental value | FALSIFIED | No improvement over O0; null degenerate/fails; M3 missingness FAIL; time holdout materially worse |
| O1_3Q persistence incremental value | FALSIFIED | No increment over O1; coverage cost |
| Operating-equity predictive signal | STOPPED | SIMPLEST_SURVIVING_MODEL=O0; PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED |
| Relax M3 (dev-vs-holdout missingness) to salvage O1 | REJECTED | Thresholds frozen pre-outcome |
| Add mapping exceptions / re-hash holdouts for O1 | REJECTED | Resolver and holdouts frozen |
| 4Q/5Q persistence / manager scores / sector tuning / ML | FROZEN | Research Stop Rule triggered |
