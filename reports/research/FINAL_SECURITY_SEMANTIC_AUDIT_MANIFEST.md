# FINAL SECURITY SEMANTIC AUDIT MANIFEST (v0.2.2)

> Generated: 2026-08-24 (outcome-blind)

## Final Status

```text
SECURITY_SEMANTIC_AUDIT_STATUS      = DELIVERED
V0_2_1_BROAD_OUTCOME_UNLOCK         = NO
V0_3_OPERATING_EQUITY_HYPOTHESIS    = JUSTIFIED_FOR_NEW_PREREGISTRATION
PARTIAL_IDENTIFICATION              = RECOMMENDED
PRODUCT_METHODOLOGY_STATUS          = NO_RULE_APPROVED
PRODUCT_CANDIDATE_STATUS            = NO_CANDIDATE
REAL_WORLD_DECISION_UTILITY         = PENDING
```

## Repository

- Baseline HEAD: `2bb12f2` (v0.2.1 final, 106 tests)
- Semantic protocol freeze SHA: `847a070`
  (`SECURITY_SEMANTIC_AUDIT_PROTOCOL_FREEZE_VERSION=v0.2.2`)
- Final HEAD: the commit containing this manifest (see git log)
- Worktree: clean after final commit

## Gates

| Gate | Result |
|---|---|
| S1 Protocol Integrity | PASS (frozen before full analysis) |
| S2 Classification Integrity | PASS (golden/unit audit; known_false_classification=0 in tested classes) |
| S3 Accounting Integrity | PASS (12,794 securities / 233,092 observations all classified or UNKNOWN) |
| S4 Outcome Blindness | PASS (no outcome/returns module in semantic path; static guard + negative test) |
| S5 Bias Audit | PASS (manager/time/direction/split/position-size/persistence quantified; shifts documented) |
| S6 Hypothesis Eligibility | JUSTIFIED_FOR_NEW_PREREGISTRATION (J1-J5 PASS with caveats) |

## Key Numbers

- Eligible universe: 12,794 securities / 233,092 O0 observations
- Operating share: 73.7% obs (68.5% common equity); Pooled share: 16.9% obs
- Operating natural resolution: O0 84.88% (vs Broad 69.97%)
- Operating missingness: 15.12% (MODERATE_CONCERN)
- Pooled is LESS persistent (2Q 21.8% vs 29.0%; 3Q 4.7% vs 9.3%) -> A1
  stability is NOT a pooled artifact
- VARIANT_MAPPING_BIAS decomposes mostly as composition effect (within
  common-stock gap <=1.8pp)
- Failure taxonomy: 49.1% of non-VERIFIED securities are
  FUND_OR_ETF_IDENTITY_PATH_MISSING

## Status Preservation

- v0.2.1 `OUTCOME_UNLOCK=NO` remains valid; no old experiment rewritten.
- This round ran no forward-return outcome; no benchmark; no null model.

