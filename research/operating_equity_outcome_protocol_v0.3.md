# Operating Equity Outcome Protocol v0.3 (PRE-REGISTERED)

> Frozen BEFORE any v0.3 forward outcome is read or computed. Changes after
> freeze require a new protocol version. This is a NEW hypothesis after an
> outcome-blind semantic audit:
> `NEW_HYPOTHESIS_AFTER_OUTCOME_BLIND_SEMANTIC_AUDIT`

## 0. Prior States (permanently preserved)

- v0.2.1 Broad: `V0_2_1_BROAD_OUTCOME_UNLOCK=NO` (valid forever; no new
  denominator, no reinterpretation).
- v0.2.2 Semantic audit: `SECURITY_SEMANTIC_AUDIT_STATUS=DELIVERED`;
  `V0_3_OPERATING_EQUITY_HYPOTHESIS=JUSTIFIED_FOR_NEW_PREREGISTRATION`.

## 1. Research Hypothesis

For 13F disclosures that are clearly operating-company equity exposure,
persistent institutional holdings behavior (2 or 3 consecutive reporting
periods) carries stable, out-of-sample, incremental economic information
relative to the simplest equal-weight institutional-action baseline, once the
information is truly public.

This is NOT a "fixed Broad experiment". It is a NEW hypothesis.

## 2. Primary Universe (frozen)

Universe membership comes ONLY from the v0.2.2 semantic manifest
(`reports/research/security_semantic_classification.csv`):

- economic_type in {OPERATING_COMMON_EQUITY, OPERATING_ADR,
  OPERATING_OTHER_EQUITY}
- AND classification_status == VERIFIED (per v0.2.2 protocol §6, only
  VERIFIED classifications enter strong analysis).

Excluded: ETF, MUTUAL_OR_POOLED_FUND, CLOSED_END_FUND, REIT/special,
PREFERRED, OTHER_13F, NON_EQUITY, UNKNOWN, and any semantic CONFLICT or
PROVISIONAL classification.

Membership is frozen at 4,790 securities (verified at baseline; see
`reports/research/v0_3_mapping_coverage.md`). It is never changed by mapping
success, future returns, manager, ticker fame, or experiment variant.

## 3. Resolver Freeze

Use the v0.2.2-era resolver state exactly. No new mapping exceptions for
coverage/sample/outcome reasons. Only documented correctness bugs may be
fixed, with audit trail and affected-sample explanation.

## 4. Eligible Observations and Variants (frozen)

- Observation construction: identical to v0.2 (position_changes put_call='',
  common window 2023-09-30..2026-06-30, effective filing info dates).
- O0 = A0 equal-weight institutional-action baseline (all eligible obs).
- O1 = A1_2Q (2-quarter persistence).
- O2 = A1_3Q (3-quarter persistence).
- No new variants, weights, thresholds, or filters.
- Universe exclusion affects only eligibility; the frozen holdout
  assignments (time/manager/security/combined) are NOT re-hashed.

## 5. Information Time (frozen)

Outcome start = `information_available_date` (effective filing date,
amendment-aware), never quarter-end. Inherited leakage guards apply.

## 6. Market Data (frozen)

- Identity: OpenFIGI + SEC resolver (unchanged).
- Price: Yahoo Chart (approved provider). Price snapshot = the v0.2.1-acquired
  local cache window (2022-01-01..2026-05-28) plus ^GSPC benchmark fetched at
  v0.3 setup. No outcome-driven refetch.
- Yahoo Search remains `NON_TRUSTED_MAPPING_SOURCE`.
- Historical identity: only VERIFIED historical identity or provider
  continuity enters; `HISTORICAL_IDENTITY_UNRESOLVED` remains missing.

## 7. Outcome Horizons and Benchmarks (frozen)

- Horizons: 3M=63, 6M=126, 12M=252 trading days (v0.2 semantics).
- Primary benchmark: S&P 500 broad proxy `^GSPC` (Yahoo adjusted close).
- Right-censored observations: `RIGHT_CENSORED_INSUFFICIENT_HORIZON`; never
  backfilled with current price.

## 8. Missingness Governance (frozen thresholds)

M1 Overall usable coverage (operating observation-level resolved): >= 80%.
M2 Per split (dev/time/manager/security/combined): >= 75%.
M3 Differential dev vs any holdout: |gap| <= 7.5pp.
M4 Directional positive vs negative: |gap| <= 7.5pp.
M5 Variant O0/O1/O2: |gap| <= 7.5pp.

These are integer governance thresholds (80/75/7.5), NOT derived from the
known ~84.9% number, and frozen before outcomes. If any gate FAILS, the
outcome may still produce descriptive artifacts, but product-candidate status
is capped at `INSUFFICIENT_MISSINGNESS_ROBUSTNESS`.

Missingness must be reported by: overall, split, direction, manager,
position-size, persistence/variant.

## 9. Missingness Sensitivity (frozen)

- Primary calculation = complete-case / resolved sample.
- Composition sensitivity: resolved vs unresolved by manager, quarter,
  action, position size, persistence.
- Partial identification: simple bounds for the directional hit rate only
  (`hit_rate_lower_bound` / `hit_rate_upper_bound`: unresolved all-miss /
  all-hit). No unbounded return bounds. No ML imputation, no outcome
  imputation, no IPW optimization.

## 10. Outcome Metrics (frozen)

Per O0/O1/O2 x horizon x split: n, coverage, absolute mean, absolute median,
excess mean, excess median, excess hit rate, downside rate, dispersion (std),
lower-tail statistic (mean of negative excess).

## 11. Null Model (frozen)

Reuse v0.2 frozen null: NULL_SEED="13f-outcome-v0.2-null", 200 repetitions,
permute signal labels within security x quarter groups, compare observed
median excess vs null 95th percentile on the development cell. Universe
membership is the only new fixed input; the null design is unchanged.

## 12. Concentration Audits (frozen)

- Manager dominance: leave-one-manager-out on dev; direction flip or top
  manager contribution -> `MANAGER_DOMINATED`.
- Security dominance: top-N contribution and leave-top-N sensitivity ->
  `SECURITY_DOMINATED`.
- Time regime: per-quarter median excess; effect in 1-2 quarters ->
  `TIME_REGIME_SENSITIVE` (no regime filter is built).
- Missingness dominance: O1/O2 advantage driven by different resolved vs
  unresolved composition -> `MISSINGNESS_SENSITIVE`.

## 13. Falsification (frozen)

O1 fails if ANY of: time holdout direction reverses; combined hard holdout
materially reverses; no meaningful improvement over O0; null comparison
fails; manager dominated; security dominated; missingness gates fail
materially; missingness sensitivity can plausibly reverse the conclusion;
downside not improved and return gain trivial; coverage cost disproportionate.

O2 additionally fails by default unless it shows clear economic increment
over O1 (selection-by-persistence is not rewarded).

## 14. Simplest Surviving Model and Product Candidate (frozen)

Order O0 -> O1 -> O2; a complex variant survives only with clear incremental
outcome, robust holdouts, acceptable missingness, no dominance. `SIMPLEST_
SURVIVING_MODEL` in {O0, O1, O2, NONE}.

Product candidate `READY_FOR_EXTERNAL_REVIEW` requires: protocol integrity,
no severe leakage, missingness governance PASS, time/manager/security/combined
holdouts robust, null supportive, no manager/security dominance, non-trivial
magnitude, complexity justified. Otherwise `NO_CANDIDATE` /
`INSUFFICIENT_EVIDENCE`. Even then: no deployment, no UI signal, no BUY/SELL,
no score, no portfolio action.

## 15. Research Stop Rule (frozen)

If O1 and O2 both fail to show robust economic incremental value over O0,
trigger `PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED`; predictive-signal research
stops (no 4Q/5Q, manager scores, sector tuning, ML) and the project converts
to Institutional Evidence System productization (docs/research_stop_rule.md).

## 16. Outcome Blindness Audit Trail

No v0.3 forward outcomes were read or computed before this protocol freeze.
Any pre-freeze outcome access, if it occurs, must be reported.

## 17. Gates (frozen)

- V1 Protocol integrity (this file frozen pre-outcome)
- V2 Hypothesis integrity (universe == v0.2.2 semantic manifest; no
  outcome-driven exclusion)
- V3 Information time / leakage (no quarter-end/amendment/future leakage)
- V4 Missingness (M1-M5 mechanical; PASS/FAIL/PASS_WITH_RESIDUAL_RISK)
- V5 Reproducibility (double-run machine artifacts identical)
- V6 O0 baseline obtained first
- V7 O1 incremental value (mechanical)
- V8 O2 incremental value (mechanical)
- V9 Simplicity (SIMPLEST_SURVIVING_MODEL in {O0,O1,O2,NONE})
- V10 Research stop (trigger check)

## 18. Freeze Marker

`V0_3_PROTOCOL_FREEZE_VERSION=v0.3`

