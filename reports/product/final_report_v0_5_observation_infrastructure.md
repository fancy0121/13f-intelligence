# 13F Institutional Intelligence System
# v0.5 Real-World Evidence Utility Observation — Infrastructure Report

> Date: 2026-08-26 | Prospective use validation (infrastructure only)

## 1. Repository

- Baseline HEAD: `dcfa839` (v0.4 final, 148 tests)
- v0.5 protocol freeze: `97103bb`
  (docs/real_world_evidence_utility_protocol_v0.5.md,
  `V0_5_REAL_USE_PROTOCOL_FREEZE_VERSION=v0.5`)
- Final HEAD: see git log; worktree clean

## 2. Final Objective

> The system exists to improve investment decision quality by providing
> accurate, independent, traceable institutional evidence and structured
> contradiction checks. It must not manufacture predictive confidence that
> the evidence does not support.

v0.5 does NOT validate alpha, future returns, or stock-picking performance.

## 3. Observation Protocol

Frozen in docs/real_world_evidence_utility_protocol_v0.5.md: episode schema,
validity rules, outcome taxonomy, misuse taxonomy, observation mix, duplicate
handling, utility metrics, threshold governance, stop/continue rules,
product-fix policy.

## 4. Episode Definition

REAL_USE_EPISODE = one real investment-research task with pre-use state
captured BEFORE product exposure, then product views, then post-use
outcomes. Pre-use fields are never rewritten by finish; subjective flags are
never auto-populated.

## 5. Pre-use / Post-use Workflow

- CLI: `obs-start` (minimal 4-field form) then `obs-finish` (8 post-use
  questions + validity determination).
- UI: Observation page (Start / Finish forms, status, export) kept separate
  from core evidence pages.
- Missing pre-use -> `INVALID_FOR_INCREMENTAL_UTILITY` / excluded.

## 6. Validity Rules

VALID / INVALID_NO_PRE_USE_CAPTURE / INVALID_SYNTHETIC_TASK /
INVALID_PRODUCT_ERROR / INVALID_DUPLICATE / INVALID_OTHER. Only VALID enters
analysis. Duplicate handling uses episode_cluster_id; report raw, unique,
clustered counts.

## 7. Utility Taxonomy

NEW_FACT_FOUND, CONTRADICTING_FACT_FOUND, STALE_ASSUMPTION_CORRECTED,
QUALITY_RISK_DISCOVERED, RESEARCH_PATH_CHANGED, RESEARCH_TIME_SAVED,
NO_INCREMENTAL_INFORMATION (legal). No composite score.

## 8. Misuse Monitoring

mISUSE_RISK NONE/LOW/MODERATE/HIGH; USER_MISINTERPRETATION vs
PRODUCT_DESIGN_INDUCED (the latter is a product defect, fix allowed).

## 9. Observation Mix Rules

Security >=8, Manager >=4, Portfolio <=8 (<=40%), unfamiliar >=5 per 20
VALID episodes; otherwise `OBSERVATION_MIX_INCOMPLETE` (no fabrication).

## 10. Stop / Continue Rules

At 20 VALID episodes, deterministic verdict SUPPORTED / MIXED /
LOW_INCREMENTAL_VALUE; below 20 -> INSUFFICIENT_OBSERVATION. No threshold
fishing; revisions only as NEXT_PROTOCOL_REVISION_CANDIDATE.

## 11. Infrastructure

- `src/thirteenf/product/observation.py`: ObservationStore (JSONL,
  append-style current-state file, local-first), product error log,
  aggregation, export CSV/JSON, product version tracking.
- CLI subcommands + Observation page.
- `data/real_use/` gitignored (episodes local).

## 12. Tests

15 new observation tests: validity (no pre-use / synthetic / product error /
duplicate), taxonomy, no-forced-utility (NO_INCREMENTAL only), subjective
fields not auto-filled, versioning, misuse, aggregation (invalid excluded,
20-valid-only), deterministic threshold verdicts (SUPPORTED / LOW), export,
product error log, no predictive dependency. Full suite 163+ tests pass.

## 13. Existing Real Episodes

Valid: 0. Invalid: 0. Pre-protocol: 0. (Fact; no fake episodes created.)

## 14. Current Observation Status

`REAL_WORLD_EVIDENCE_UTILITY=INSUFFICIENT_OBSERVATION` (0 VALID / target 20).
Status page shows the banner until 20 valid episodes.

## 15. What Has NOT Been Validated

- Real-world information utility (Level 1/2) - unobserved.
- Real-user misuse behavior - unobserved.
- Any predictive value - explicitly excluded.

## 16. Recommended Human Next Step

Use the product for real research tasks and record episodes via the
Observation page or CLI. At 5/10 valid episodes run safety/product-defect
review. At 20 valid episodes read the verdict. Do not add product features.

## 17. Final Status

```text
PREDICTIVE_RESEARCH_STOP_RULE              = TRIGGERED
PREDICTIVE_PRODUCT_SIGNAL_STATUS           = DISABLED
EVIDENCE_PRODUCT_STATUS                    = CANDIDATE_READY_FOR_REAL_USE
REAL_USE_OBSERVATION_INFRASTRUCTURE_STATUS = DELIVERED
REAL_WORLD_EVIDENCE_UTILITY                = INSUFFICIENT_OBSERVATION
REAL_WORLD_DECISION_UTILITY                = PENDING
```

