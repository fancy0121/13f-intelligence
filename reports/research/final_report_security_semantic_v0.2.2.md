# 13F Institutional Intelligence System
# Security Semantic Audit v0.2.2 — Final Report

> Date: 2026-08-24 | Mode: autonomous, outcome-blind

## 1. Repository

- Baseline HEAD: `2bb12f2` (v0.2.1 final, 106 tests)
- Semantic protocol freeze: `847a070`
  (research/security_semantic_audit_protocol_v0.2.2.md,
  `SECURITY_SEMANTIC_AUDIT_PROTOCOL_FREEZE_VERSION=v0.2.2`)
- Final HEAD: see git log (commit containing this report)
- Worktree clean; no secrets; no outcome artifacts

## 2. Prior State Preservation

- v0.2.1 `BROAD_13F_OUTCOME_UNLOCK=NO` (coverage 69.97/73.84/77.35%,
  split/differential/variant bias FAIL) remains valid and unchanged.
- No old protocol or experiment was rewritten; no denominator redefined.

## 3. Outcome Blindness

- Not viewed/used: forward returns, benchmark-relative returns, hit rates,
  null-model outcomes, 3M/6M/12M prices for research, future labels.
- Guards: semantic package imports no `research.outcomes` module; no
  `forward_return`/`null_model`/`benchmark` in semantic source; static guard
  test `test_outcome_blindness_static_guard`; classifier has no resolution or
  ticker inputs (test).

## 4. Universe Composition (Q1)

Observation level (O0, 233,092): OPERATING_COMMON_EQUITY 68.47%,
OPERATING_ADR 4.65%, OPERATING_OTHER_EQUITY 0.54% (operating 73.66%);
ETF 14.72%, MUTUAL_OR_POOLED_FUND 1.62%, CLOSED_END_FUND 0.60% (pooled
16.94%); UNKNOWN 4.10%; REIT/special 2.96%; non-equity 1.74%; others small.

## 5. Variant Composition (Q2)

O1_2Q: common equity 71.83%, ETF 11.85%; O1_3Q: common equity 75.27%,
ETF 8.28%. Persistence variants are more common-stock-heavy -> composition
effect consistent with variant mapping bias.

## 6. Split Composition (Q3)

`SECURITY_TYPE_SPLIT_SHIFT=True`: H0_dev has ETF 19.24% (vs overall 14.72%,
+4.5pp) and common equity 62.84% (vs 68.47%, -5.6pp). Split structure differs
by security type; relevant for future holdout design.

## 7. Resolution By Economic Type (Q4)

Resolver VERIFIED rate (v0.2.1 rules unchanged): OPERATING_COMMON_EQUITY
74.92%, OPERATING_ADR 65.47%, REIT 90.19%, OPERATING_OTHER 24.36%; ETF
16.85%, MUTUAL_OR_POOLED 3.84%, CLOSED_END 7.50%, UNKNOWN 34.03%. Pooled
types are the dominant low-resolution group.

## 8. Failure Taxonomy (Q5)

6,766 non-VERIFIED securities: FUND_OR_ETF_IDENTITY_PATH_MISSING 3,322
(49.1%), UNKNOWN_REASON 1,226 (18.1%), NAME_OR_ENTITY_CONFLICT 681 (10.1%),
DELISTED_OR_TERMINATED 679 (10.0%), NON_EQUITY 442 (6.5%),
OPENFIGI_MULTI_MATCH 246 (3.6%), SEC_CORROBORATION_MISSING 138 (2.0%),
ADR_OR_ORDINARY_AMBIGUITY 32 (0.5%). The "5,365 unresolved" is now a
structured, explainable taxonomy.

## 9. Operating Equity Natural Resolution (Q6)

Audit-only view; resolver NOT modified. Operating securities 6,509; VERIFIED
4,699 (72.2%). Observation coverage O0 84.88%, O1_2Q 86.17%, O1_3Q 86.62%;
per-split worst 79.26% (dev) / 79.56% (security holdout). Higher than Broad
but STILL below the frozen 90% threshold.

## 10. Operating vs Pooled Behavior (Q7) — pre-outcome facts

Pooled has higher NEW (30.4% vs 21.2%) and EXIT (20.9% vs 9.8%) rates, higher
turnover (0.533 vs 0.325), higher reversal (67.7% vs 55.7%), lower persistence
(2Q 21.8% vs 29.0%; 3Q 4.7% vs 9.3%), ~10x smaller positions, fewer managers
per security (1.5 vs 4.5). `MANAGER_COMPOSITION_CONFOUNDED=False`;
`TIME_COMPOSITION_SENSITIVE=True` (quarterly positive-rate gap -5.1..+8.7pp;
structural descriptors stable).

## 11. Confounding

- Manager: within-manager control shows mixed differences; gap not driven by
  a few managers.
- Time: quarterly action-rate gap sensitive; structure stable.
- Position size: pooled positions ~10x smaller; recorded; never interpreted
  as conviction.

## 12. Persistence Composition (§27)

Pooled vehicles are LESS persistent than operating equities. A1's stability
is NOT a pooled-universe artifact; operating equities themselves show the
same/higher persistence pattern.

## 13. Missingness (§30)

`OPERATING_EQUITY_MISSINGNESS_STATUS=MODERATE_CONCERN` (15.12%). Direction
gap small; dev/security holdout ~20%; early quarters higher (22.8% -> 8.1%).
Must be handled by bounds in any v0.3.

## 14. Variant Mapping Bias Decomposition (§29)

Overall: O0 69.97 / O1_2Q 73.84 / O1_3Q 77.35. Within common equity: 85.43 /
86.73 / 87.25 (gap <=1.8pp). The v0.2.1 VARIANT_MAPPING_BIAS is mostly a
security-type COMPOSITION effect; within-type bias is small.

## 15. Selection Bias (§28)

Manager deltas small except manager 26 (36.4% -> 28.4%, -8.0pp, the
ETF-heavy manager); quarter deltas <0.5pp; direction small. No unacceptable
distortion; shifts documented.

## 16. Partial Identification Recommendation

`RECOMMENDED` - worst/best-case bounds for ~15% unresolved operating
observations in any future v0.3. Not implemented this round.

## 17. Hypothesis Eligibility (J1-J5)

J1 PASS (economic semantics distinct); J2 PASS (structural behavioral
distinction; caveat time-sensitivity); J3 PASS (not mapping convenience);
J4 PASS (shifts documented; missingness moderate); J5 PASS (directly
related to institutional stock-selection evidence).

```text
V0_3_OPERATING_EQUITY_HYPOTHESIS=JUSTIFIED_FOR_NEW_PREREGISTRATION
```

Per protocol §47, this round STOPS: no v0.3 outcome, no v0.3 protocol freeze,
no product rule.

## 18. Research Stop Rule

Frozen in `docs/research_stop_rule.md` (and referenced in
`docs/rejected_or_frozen_ideas.md`): predictive-signal research stops if the
broad hypothesis fails, v0.3 is completed, and frozen outcome tests show no
incremental value; system converts to an Institutional Evidence System.

## 19. Gates Summary

| Gate | PASS/FAIL |
|---|---|
| S1 Protocol Integrity | PASS |
| S2 Classification Integrity | PASS |
| S3 Accounting Integrity | PASS |
| S4 Outcome Blindness | PASS |
| S5 Bias Audit | PASS |
| S6 Hypothesis Eligibility | JUSTIFIED_FOR_NEW_PREREGISTRATION |

## 20. Final Verdict / Status

```text
SECURITY_SEMANTIC_AUDIT_STATUS      = DELIVERED
V0_2_1_BROAD_OUTCOME_UNLOCK         = NO
V0_3_OPERATING_EQUITY_HYPOTHESIS    = JUSTIFIED_FOR_NEW_PREREGISTRATION
PRODUCT_METHODOLOGY_STATUS          = NO_RULE_APPROVED
PRODUCT_CANDIDATE_STATUS            = NO_CANDIDATE
REAL_WORLD_DECISION_UTILITY         = PENDING
```

## 21. Recommended Next Step

External review. If approved, launch a SEPARATE v0.3 preregistration
(outcome-blind, fresh protocol) for an operating-equity hypothesis, including
its own coverage/eligibility policy, missingness bounds, and time-regime
checks. This round does not start it.

