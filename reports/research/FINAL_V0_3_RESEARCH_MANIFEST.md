# FINAL v0.3 RESEARCH MANIFEST

> Generated: 2026-08-26 | Operating Equity Outcome Validation (frozen protocol)

## Final Status

```text
V0_3_OUTCOME_VALIDATION_STATUS    = DELIVERED
MISSINGNESS_GOVERNANCE_STATUS     = FAIL        (M3 differential missingness)
SIMPLEST_SURVIVING_MODEL          = O0
PRODUCT_METHODOLOGY_STATUS        = NO_RULE_APPROVED
PRODUCT_CANDIDATE_STATUS          = NO_CANDIDATE
PREDICTIVE_RESEARCH_STOP_RULE     = TRIGGERED
REAL_WORLD_DECISION_UTILITY       = PENDING
```

## Repository

- Baseline HEAD: `05e1f70` (v0.2.2 final, 118 tests)
- v0.3 protocol freeze SHA: `ad4139a`
  (`V0_3_PROTOCOL_FREEZE_VERSION=v0.3`)
- Final HEAD: the commit containing this manifest (see git log)
- Worktree: clean after final commit

## Hypothesis

`NEW_HYPOTHESIS_AFTER_OUTCOME_BLIND_SEMANTIC_AUDIT` - operating equity 13F
evidence hypothesis (O0/A0 baseline, O1/A1_2Q, O2/A1_3Q persistence).

## Universe (v0.2.2 semantic manifest, VERIFIED operating only)

- 4,790 securities: OPERATING_COMMON_EQUITY 4,364, OPERATING_ADR 382,
  OPERATING_OTHER_EQUITY 44.
- O0 eligible observations (operating): 147,940.
- Observation mapping coverage: O0 90.41% / O1_2Q 91.04% / O1_3Q 91.41%.

## Missingness Gates (M1-M5)

| Gate | Value | PASS |
|---|---|---|
| M1 overall >=80% | 90.41% | PASS |
| M2 per-split >=75% | 85.9-94.3% | PASS |
| M3 dev vs holdouts <=7.5pp | up to 8.42pp | **FAIL** |
| M4 directional <=7.5pp | 2.15pp | PASS |
| M5 variant <=7.5pp | <=1.0pp | PASS |

## Outcome Verdict

- O0 dev 3M excess median: -2.62% (n=36,873; hit rate 44.2%)
- O1_2Q dev 3M excess median: -2.83% (no improvement over O0)
- O1_3Q dev 3M excess median: -3.07% (no increment over O1)
- Time holdout 3M: O1 -10.2% vs O0 -3.3% (materially worse)
- Null comparison: degenerate on this universe (observed == null p95) - no
  advantage
- O1 fail: NO_MEANINGFUL_IMPROVEMENT_OVER_O0, NULL_COMPARISON_FAILS,
  MISSINGNESS_GATES_FAIL
- O2 fail: same + NO_INCREMENT_OVER_O1
- `SIMPLEST_SURVIVING_MODEL=O0`; `PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED`;
  `PRODUCT_CANDIDATE_STATUS=NO_CANDIDATE`

## Prior States Preserved

- v0.2.1 `V0_2_1_BROAD_OUTCOME_UNLOCK=NO` (permanent).
- v0.2.2 `SECURITY_SEMANTIC_AUDIT_STATUS=DELIVERED`;
  `V0_3_OPERATING_EQUITY_HYPOTHESIS=JUSTIFIED_FOR_NEW_PREREGISTRATION`
  (the justification for running v0.3; v0.3 is now complete and falsified).

## Next Step

Per docs/research_stop_rule.md: predictive-signal research stops. The system
converts to an Institutional Evidence System (productization of factual
evidence). External review of this manifest and the final report is required
before any further research direction.

