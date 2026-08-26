# 13F Institutional Intelligence System
# v0.3 Operating Equity Outcome Validation — Final Report

> Date: 2026-08-26 | Autonomous execution, frozen protocol

## 1. Repository

- Baseline HEAD: `05e1f70` (v0.2.2 final, 118 tests)
- v0.3 protocol freeze: `ad4139a`
  (research/operating_equity_outcome_protocol_v0.3.md,
  `V0_3_PROTOCOL_FREEZE_VERSION=v0.3`)
- Final HEAD: see git log (commit containing this report); worktree clean

## 2. Hypothesis

`NEW_HYPOTHESIS_AFTER_OUTCOME_BLIND_SEMANTIC_AUDIT`:
for operating-company equity exposures, persistent institutional behavior
(2Q/3Q) carries stable out-of-sample incremental economic information vs the
simplest equal-weight institutional-action baseline (O0).

## 3. Prior Failure Preservation

- v0.2.1 Broad `V0_2_1_BROAD_OUTCOME_UNLOCK=NO` remains valid; no old
  experiment or denominator rewritten.
- v0.2.2 semantic audit remains the factual basis that justified this v0.3
  preregistration.

## 4. Universe

4,790 securities from the v0.2.2 semantic manifest (OPERATING types with
VERIFIED classification): COMMON 4,364 / ADR 382 / OTHER 44. O0 eligible
observations: 147,940. No ETF/UNKNOWN/CONFLICT/PROVISIONAL leakage (Gate V2).

## 5. Missingness (Gate V4)

- Overall resolved: O0 90.41% / O1_2Q 91.04% / O1_3Q 91.41% (M1 PASS).
- Per split (O0): dev 85.88%, time 94.30%, manager 90.04%, security 86.04%,
  combined 93.88% (M2 PASS).
- M3 **FAIL**: dev vs time holdout 8.42pp; dev vs combined 8.00pp (limit
  7.5pp). Development has structurally lower coverage (earlier quarters /
  security holdout).
- M4 directional 2.15pp PASS; M5 variant <=1.0pp PASS.
- `MISSINGNESS_GOVERNANCE_STATUS=FAIL`.
- Manager-specific missingness: 3.5%..39% (small managers highest); quarter
  missing declines 22.8% -> 8.1%; direction positive 8.7pp vs negative 10.9pp.

## 6. Outcome Samples and Right-Censoring

- 3M resolved: O0 103,773; 6M 86,364; 12M 53,012 (right-censored 29,583 /
  46,989 / 80,345).
- O1_2Q: 27,467 / 21,110 / 16,982. O1_3Q: 6,271 / 4,806 / 3,512.
- 12M time/combined cells have 0 returns (insufficient forward window after
  the price snapshot 2026-05-28) - reported as empty, never backfilled.

## 7. O0 Baseline (Gate V6 - obtained)

Dev 3M: mean +1.80%, median -2.62%, hit 44.2%, downside rate 55.8%,
mean_negative -16.3%. 6M/12M: median -4.94% / -10.38%. Holdouts all negative
median (time -3.3%, manager -3.5%, security -2.4%, combined -3.0%).

## 8. O1_2Q (Gate V7 - FAIL)

Dev 3M median -2.83% (worse than O0 by 0.21pp -> NO_MEANINGFUL_IMPROVEMENT).
Time holdout 3M median -10.23% vs O0 -3.28% (materially worse). Null
comparison degenerate (observed == null p95; no advantage). Missingness M3
FAIL. Manager dominance: not flagged after n_obs fix (top security share
0.2%). O1 does not survive.

## 9. O1_3Q (Gate V8 - FAIL)

Dev 3M median -3.07%; no increment over O1 (NO_INCREMENT_OVER_O1). Same
failure set as O1. Coverage cost: O1_3Q 3M n=6,271 vs O0 103,773 (6%).

## 10. Holdouts

O1 time/combined holdout 3M medians -10.2% / -9.7% vs O0 -3.3% / -3.0%:
persistence does not generalize to time/combined holdouts on this universe.

## 11. Null

Frozen null (NULL_SEED, 200 reps, dev cell). Degenerate on the operating
universe (most security x quarter cells are singletons -> permuted medians
equal observed). No variant exceeds null p95. Reported as a limitation, not
as evidence of signal.

## 12. Concentration

- Manager: 16 managers in dev; leave-one-manager-out shows no direction flip
  dominance (top share of single manager not dominant).
- Security: top security observation share <1% (not SECURITY_DOMINATED after
  n_obs fix).
- Time regime: dev 3M medians range -5.4%..+1.8% across quarters;
  `TIME_REGIME_SENSITIVE` (no regime filter built).

## 13. Missingness Sensitivity

Resolved vs unresolved composition within operating: manager gaps 3.5-39%
(small managers highest); quarter missing declines over time; direction gap
~2pp; split dev/security ~14-15% missing vs time/combined ~6-10%. The O1/O2
null result is not attributable to a single manager; but M3 (dev vs holdout)
means the resolved-sample is not composition-balanced across splits. No
missingness-reversal evidence for O1 (O1 is worse, so missingness cannot
"reverse" an advantage that does not exist).

## 14. Falsification

O1: FAIL (no improvement, null fails, missingness M3 fail). O2: FAIL (same +
no increment over O1). Both falsified on pre-registered criteria.

## 15. Simplest Surviving Model

`SIMPLEST_SURVIVING_MODEL=O0`

## 16. Research Stop Rule

`PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED`. Per docs/research_stop_rule.md,
predictive-signal research stops: no 4Q/5Q persistence, no manager scores, no
sector tuning, no ML, no new feature search. Project converts to an
Institutional Evidence System.

## 17. Product Candidate

`PRODUCT_CANDIDATE_STATUS=NO_CANDIDATE`. No deployment, no UI signal, no
BUY/SELL, no score, no portfolio action.

## 18. Gates Summary

| Gate | Result |
|---|---|
| V1 Protocol Integrity | PASS |
| V2 Hypothesis Integrity | PASS |
| V3 Information Time / Leakage | PASS |
| V4 Missingness | **FAIL** (M3) |
| V5 Reproducibility | PASS (double-run identical) |
| V6 O0 Baseline | PASS (obtained) |
| V7 O1 Incremental | FAIL |
| V8 O2 Incremental | FAIL |
| V9 Simplicity | O0 |
| V10 Research Stop | TRIGGERED |

## 19. What We Should NOT Build

- Do NOT keep searching predictive signals after the stop rule.
- Do NOT relax M3/7.5pp to salvage O1.
- Do NOT add mapping exceptions or re-hash holdouts.
- Do NOT revive A2/A3/manager scores.
- Do NOT interpret the negative medians as "buy the opposite" (13F is not a
  trade signal).

## 20. Remaining Risks

- M3 missingness gap (dev vs time/combined) limits cross-split inference even
  for O0.
- Null is degenerate on this universe; null-based falsification is weak.
- 12M right-censoring leaves long-horizon cells empty.
- Yahoo price snapshot ends 2026-05-28 (fixed before outcomes; not refetched).

## 21. Final Status

```text
V0_3_OUTCOME_VALIDATION_STATUS    = DELIVERED
MISSINGNESS_GOVERNANCE_STATUS     = FAIL
SIMPLEST_SURVIVING_MODEL          = O0
PRODUCT_METHODOLOGY_STATUS        = NO_RULE_APPROVED
PRODUCT_CANDIDATE_STATUS          = NO_CANDIDATE
PREDICTIVE_RESEARCH_STOP_RULE     = TRIGGERED
REAL_WORLD_DECISION_UTILITY       = PENDING
```

## 22. Recommended Next Step

External review. If confirmed, transition to Institutional Evidence System
productization: holdings history, NEW/ADD/REDUCE/EXIT facts, portfolio-weight
facts, persistence facts, reverse lookup, freshness/amendment awareness,
provenance and quality - none of which depend on outcome success.

