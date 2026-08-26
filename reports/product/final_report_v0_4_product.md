# 13F Institutional Intelligence System
# v0.4 Minimum Institutional Evidence Product — Final Report

> Date: 2026-08-26 | Product Anti-Overfitting Harness

## 1. Repository

- Baseline HEAD: `f55eba4` (v0.3 final, 125 tests)
- Product protocol freeze: `b44b2c3`
  (docs/product_protocol_v0.4.md, `V0_4_PRODUCT_PROTOCOL_FREEZE_VERSION=v0.4`)
- Final HEAD: see git log; worktree clean

## 2. Final Objective (confirmed)

> The system exists to improve investment decision quality by providing
> accurate, independent, traceable institutional evidence and structured
> contradiction checks. It must not manufacture predictive confidence that
> the evidence does not support.

## 3. Research Governance

`PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED`; no predictive research was
repackaged. `PREDICTIVE_PRODUCT_SIGNAL_STATUS=DISABLED`.

## 4. Product Scope

Three scenarios only: A Manager (what changed), B Security (who changed),
C My Portfolio (what facts am I missing). No price/valuation/news/trading.

## 5. What Was Removed

- Deleted `app/db.py` (exposed consensus/trends/scoring), `pages/consensus.py`,
  `pages/stocks.py` (consensus/trend sections).
- Product pages no longer reference `consensus_score`, `trend_label`,
  `scoring_status`, `signal_quality`; no evidence/confidence score is shown.
- Predictive residue audit: product code clean; only negation/disclaimer and
  forbidden-list-context hits remain in app/docs.

## 6. Product Architecture

- `src/thirteenf/product/evidence.py` - deterministic queries + derived facts
  (FACT/DERIVED FACT), DTOs, independence (holder_entity_count vs
  verified_independent_manager_count), persistence with no gap crossing,
  freshness, amendment, quality.
- `src/thirteenf/product/tasks.py` - task universe + dev/holdout split.
- `app/` - thin Streamlit pages over the product layer; no live external calls.

## 7. Product Task Holdout

412 tasks (15 categories incl. ADR, share class, stale, unfamiliar,
unresolved/ambiguous, manager amended/incomplete). Dev 277 / holdout 135 by
SHA256 hash (`13f-product-v0.4-task`). This is a product-robustness holdout,
not predictive.

## 8. Scenario A - Manager

Manager page: filing status (period/date/age/stale/amended), snapshot (position
count/total value/top holdings), latest NEW/ADD/REDUCE/EXIT tables, repeated
activity, quality (unresolved/missing periods). Verified on holdout manager
tasks.

## 9. Scenario B - Security

Security page: identity (issuer/ticker/CUSIP/class/resolution), freshness,
holder table with symmetric action display, activity counts, repeated counts,
timeline, quality. Search by ticker/CUSIP/issuer; multiple matches all shown
(no first-result). Verified on holdout security tasks.

## 10. Scenario C - My Portfolio

Empty portfolio -> `SETUP_REQUIRED` (no demo data). Symmetry rule: adds,
reduces, exits, repeated-adds, repeated-reduces all shown with 0 when absent.
No thesis inference.

## 11-19. Gates P1-P10

- P1 Fact integrity: golden tests compare UI facts to DB (0 mismatch).
- P2 Derived integrity: counts/breadth/persistence/freshness deterministic.
- P3 Predictive isolation: static + negative tests; product imports no
  outcome/null/falsification modules.
- P4 Symmetry: security/portfolio show both directions; absent side = 0.
- P5 Quality transparency: resolution status, stale, amendment, missing
  periods visible.
- P6 Holdout robustness: dev 277/277, holdout 135/135 retrievable; no task
  replaced.
- P7 Retrieval utility: pre-registered questions answerable (identity,
  freshness, holders, activity, repeated, quality).
- P8 My Portfolio: `PARTIAL_EMPTY_PORTFOLIO` (no fake data).
- P9 No forced insight: neutral/insufficient states allowed and tested.
- P10 Regression: full pytest green (production, anti-overfitting, resolution,
  semantic, v0.3, product); stop rule preserved.

## 20. Predictive Residue Audit

`reports/product/predictive_residue_audit.md` - product code clean; app hits
are negations ("不做任何买卖建议", "不产生任何预测性信号"); docs hits are
forbidden-list/explanations only.

## 21. Known Weaknesses

- Independence is governance-sourced (managers.csv validation status); a
  manager family not yet scoped would default to independent.
- Persistence counts stop at gap quarters (conservative by design).
- Resolution coverage for identity is ~47% of all securities; product always
  shows the status rather than hiding.
- Real-user information value is unobserved (Layer B pending).

## 22. Real-World Utility Protocol

`docs/real_world_evidence_utility_protocol.md` frozen for future sessions;
`REAL_WORLD_EVIDENCE_UTILITY=PENDING_OBSERVATION`. `NO_INCREMENTAL_INFORMATION`
is a legal outcome.

## 23. What The Product Does NOT Claim

- No recommendation, no bullish/bearish, no conviction, no smart money, no
  predictive persistence, no "surviving model" claim, no evidence score.
- 13F data is delayed, long-only, and incomplete (shorts/derivatives/cost
  basis absent).

## 24. Recommended Next Step

External review, then real-user observation per the utility protocol. Do not
deploy or add predictive features.

## 25. Final Status

```text
PREDICTIVE_RESEARCH_STOP_RULE        = TRIGGERED
PREDICTIVE_PRODUCT_SIGNAL_STATUS     = DISABLED
PRODUCT_ANTI_OVERFITTING_HARNESS_STATUS = DELIVERED
EVIDENCE_PRODUCT_STATUS              = CANDIDATE_READY_FOR_REAL_USE
PRODUCT_METHODOLOGY_STATUS           = EVIDENCE_ONLY
REAL_WORLD_EVIDENCE_UTILITY          = PENDING_OBSERVATION
REAL_WORLD_DECISION_UTILITY          = PENDING
```

