# PRODUCT v0.4 MANIFEST — Minimum Institutional Evidence Product

> Generated: 2026-08-26 | Evidence-only product + anti-overfitting harness

## Final Status

```text
PREDICTIVE_RESEARCH_STOP_RULE        = TRIGGERED
PREDICTIVE_PRODUCT_SIGNAL_STATUS     = DISABLED
PRODUCT_ANTI_OVERFITTING_HARNESS_STATUS = DELIVERED
EVIDENCE_PRODUCT_STATUS              = CANDIDATE_READY_FOR_REAL_USE
PRODUCT_METHODOLOGY_STATUS           = EVIDENCE_ONLY
REAL_WORLD_EVIDENCE_UTILITY          = PENDING_OBSERVATION
REAL_WORLD_DECISION_UTILITY          = PENDING
```

## Repository

- Baseline HEAD: `f55eba4` (v0.3 final, 125 tests)
- Product protocol freeze SHA: `b44b2c3` (`V0_4_PRODUCT_PROTOCOL_FREEZE_VERSION=v0.4`)
- Final HEAD: the commit containing this manifest (see git log)
- Worktree: clean after final commit

## Gates

| Gate | Result |
|---|---|
| P1 Fact Integrity | PASS (golden tests: UI facts == DB exact) |
| P2 Derived Evidence Integrity | PASS (deterministic counts/breadth/persistence/freshness) |
| P3 Predictive Isolation | PASS (product modules import no outcome/null/falsification; no forbidden language; static tests) |
| P4 Symmetry / Confirmation-Bias Control | PASS (adds/reduces/exits shown equally; zeros visible) |
| P5 Data Quality Transparency | PASS (resolution/amendment/stale shown per scope) |
| P6 Cross-Task Robustness | PASS (dev 277/277, holdout 135/135 retrievable) |
| P7 Retrieval Utility | PASS (A/B/C answers retrievable on holdout tasks) |
| P8 My Portfolio | PASS_WITH_PARTIAL (empty portfolio -> SETUP_REQUIRED; no fabricated data) |
| P9 No Forced Insight | PASS (neutral states allowed) |
| P10 Regression | PASS (full pytest; stop rule preserved) |

## Product Scope Delivered

- 6 pages: Overview, Managers, Securities, Activity Explorer, My Portfolio,
  Methodology (no consensus/scores/trends page).
- Product query layer `src/thirteenf/product/` (deterministic, offline).
- Task pool: 412 tasks (15 categories), dev 277 / holdout 135
  (`product_task_manifest.csv`).
- Query snapshot deterministic (checksum `46F33053...`).
- Predictive residue audit: product code clean; app/doc hits are only
  negations/forbidden-list context.

## Prior States Preserved

- v0.2.1 `V0_2_1_BROAD_OUTCOME_UNLOCK=NO`
- v0.2.2 `SECURITY_SEMANTIC_AUDIT_STATUS=DELIVERED`
- v0.3 `SIMPLEST_SURVIVING_MODEL=O0`, `PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED`

## Next Step

Real-user observation under `docs/real_world_evidence_utility_protocol.md`
after external review. Do NOT deploy, activate UI signals, or turn on any
predictive feature.

