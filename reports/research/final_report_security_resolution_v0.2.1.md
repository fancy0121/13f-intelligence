# 13F Institutional Intelligence System
# Security Resolution Validation & Frozen Outcome Unlock — Final Report

> Date: 2026-08-24
> Mode: autonomous execution (no staged questions)

## 1. Repository

- Baseline HEAD: `32a782c2285644cf141577af7be10033353a1a08` (72 tests)
- Resolution protocol freeze: `4a53ab1` (research/security_resolution_protocol_v0.2.1.md,
  `SECURITY_RESOLUTION_PROTOCOL_FREEZE_VERSION=v0.2.1`)
- Pilot + resolver: `5d14f88`, `a56ccf5`
- Final HEAD: see git log (the commit containing this report)
- Worktree: clean after final commit; no secrets; no raw/large caches in git

## 2. What Was Done (summary)

Built the auditable, multi-source, time-aware CUSIP -> market instrument
resolution layer, ran it over the full outcome-eligible universe, and
mechanically evaluated the frozen unlock gates. The outcome experiment was
**not** executed because the frozen gates failed - no fabricated outcomes.

## 3. Provider Capability (per function)

| Provider | Identity | Price | Benchmark | Corp Actions | Historical Continuity |
|---|---|---|---|---|---|
| SEC company-tickers* | PASS (issuer/CIK/current ticker) | n/a | n/a | n/a | PARTIAL (current only) |
| OpenFIGI ID_CUSIP/8/ISIN | PASS (unique shareClassFIGI + US ticker) | n/a | n/a | n/a | FAIL for historical symbols |
| Yahoo Search | FAIL / NON_TRUSTED | n/a | n/a | n/a | n/a |
| Yahoo Chart | n/a | PASS | PASS (^GSPC) | PASS (adjclose+splits+div) | PASS (provider continuity) |
| Stooq | FAIL | FAIL | n/a | n/a | n/a |

`APPROVED_MAPPING_PROVIDER=OpenFIGI` (+SEC corroboration);
`APPROVED_PRICE_PROVIDER=Yahoo Chart`.

## 4. Correction of Previous Assumptions

- **RETRACTED**: "OpenFIGI anonymous does not support CUSIP/ISIN". Correct
  enums are `ID_CUSIP` / `ID_CUSIP_8_CHR` / `ID_ISIN`; live tests resolved
  19/20 pilot CUSIPs with US-venue filtering (see openfigi_identifier_audit.md).
- **CONFIRMED**: Yahoo chart price capability (adjusted close, splits,
  ^GSPC, 404) and Yahoo search non-trust for identity.
- **REFINED**: price-provider and mapping-provider are independent; the
  blanket `NO_APPROVED_PROVIDER` was retired.

## 5. Pilot (Gate R3)

- Part A fixed cases: GOOGL (share class), TSM (ADR), Block (SQ->XYZ), PDD,
  FLUT - all resolved correctly (previous failures fixed).
- Part B: 50 deterministic blind CUSIPs.
- Status: VERIFIED_EXACT 13, VERIFIED_MULTI_SOURCE 12, NON_EQUITY 4,
  UNRESOLVED 26.
- Golden audit: 25/25 VERIFIED records consistent with OpenFIGI name, SEC
  title, and 13F issuer; **known_false_verified = 0** -> Gate R3 PASS.

## 6. Historical Identity (Gate R4)

- Share classes: GOOGL vs GOOG differentiated by CUSIP (never merged).
- ADR: TSM / PDD securityType=ADR consistent with "SPONSORED ADS" titles.
- Rename: Block current symbol XYZ returns full 2022+ history (provider
  continuity); old tickers (SQ, FB) never used blindly (FB is reused by
  another issuer; SQ dead).
- Class-share price format: OpenFIGI `BRK/B` -> Yahoo `BRK-B` deterministic
  conversion added; 15 class shares recovered; 4 warrants genuinely
  unavailable (404) and excluded.
- 208 verified securities whose price history does not reach their earliest
  observation date are excluded (HISTORICAL_IDENTITY_UNRESOLVED) - no
  backfilling.

## 7. Coverage (Gate R5) - FAIL

Frozen denominator = original eligible observations (matches the frozen
outcome manifest exactly: O0 233,092 / O1_2Q 64,262 / O1_3Q 19,634).

| Variant | Overall | H0_dev | H1_time | H2_manager | H3_security | H4_combined |
|---|---|---|---|---|---|---|
| O0 | 69.97% | 61.97% | 67.28% | 79.12% | 62.41% | 79.38% |
| O1_2Q | 73.84% | 66.19% | 73.95% | 83.81% | 66.36% | 83.25% |
| O1_3Q | 77.35% | 69.31% | 80.50% | 87.37% | 69.03% | 84.51% |

Security-level coverage: 6,028/12,794 (47.1%). All variants below the frozen
90% overall / 85% per-split thresholds.

## 8. Bias (Gate R6) - FAIL

- Differential: dev vs holdout up to ~17pp (frozen max 5pp).
- Positive vs negative activity: O0 71.15% vs 68.04% (within 5pp) - PASS.
- **VARIANT_MAPPING_BIAS**: O1_3Q 77.35% vs O0 69.97% (7.4pp) - persistence
  variants resolve better because they are common-stock-heavy. A fair
  O0-vs-O1 comparison is not possible under current rules.
- Frequency: high-frequency securities verify at 67.1%, low-frequency at
  26.2% - reported, material.

## 9. Manual Queue

- 959 rows (AMBIGUOUS 743 / CONFLICT 216), impacting 7,099 observations
  (3.0% of O0). Sorted by observation impact.
- Top items are genuine conflicts (T. Rowe Price, BJS Restaurants) and
  multi-venue ambiguities (Grab, Liberty Global, Valaris, U-Haul).
- The 5,365 UNRESOLVED (mostly funds/delisted) are NOT pushed to the user;
  they are reported as counts with reasons.

## 10. OUTCOME_UNLOCK = NO

Precise blockers (not a request for a full CSV):

1. Frozen 90% observation coverage is unreachable under v0.2.1 rules: ~25% of
   eligible observations are funds/ETFs that cannot be VERIFIED because SEC
   company-ticker files lack most fund tickers and 13F title_of_class is
   truncated; plus a tail of delisted/foreign/no-US-venue equities.
2. Differential coverage dev-vs-holdout exceeds 5pp.
3. VARIANT_MAPPING_BIAS (O1/O2 > O0 by >5pp).

Minimal path: a `NEXT_PROTOCOL_CANDIDATE` fund-verification rule and/or a
curated Tier-4 fund table for top high-observation funds, then re-running the
same frozen gates. Manual review of the 964-row queue alone recovers at most
3% and is insufficient.

## 11. Product Candidate

`PRODUCT_CANDIDATE_STATUS=NO_CANDIDATE` (unchanged). Product layer remains
frozen; nothing is promoted from research.

## 12. Gates Summary

| Gate | PASS/FAIL |
|---|---|
| R1 Protocol Integrity | PASS |
| R2 Provider Truth | PASS |
| R3 False Mapping | PASS (0 false VERIFIED) |
| R4 Historical Identity | PASS |
| R5 Coverage | FAIL |
| R6 Mapping Bias | FAIL |
| R7 Outcome Unlock | NO |

## 13. What We Should NOT Build

- Do NOT auto-promote any outcome rule while coverage/bias gates fail.
- Do NOT lower the 90%/85%/5pp thresholds to "make it work".
- Do NOT use Yahoo Search or LLM for identity; do not use old tickers blindly.
- Do NOT build a heavyweight MDM/microservice/graph stack - Python + SQLite +
  pandas + requests is sufficient.

## 14. Remaining Risks

- Fund/ETF resolution requires a rule change or curated fund table (external
  decision).
- Yahoo is unofficial for bulk retrieval (research-only, local caching).
- SEC ticker associations are not guaranteed complete (documented).
- Future renames/delistings require re-running the resolution pipeline.
- 12M outcome horizon will remain right-censored until enough forward time
  passes even after unlock.

## 15. Next Step

External review of this report; decision on a `NEXT_PROTOCOL_CANDIDATE` for
fund verification; optional manual review of the 964-row queue; then re-run
the frozen unlock gates.

## 16. Final Status

```text
SECURITY_RESOLUTION_HARNESS_STATUS = DELIVERED
OUTCOME_UNLOCK                    = NO
OUTCOME_VALIDATION_STATUS         = PARTIAL_COVERAGE_GATES_FAIL
PRODUCT_METHODOLOGY_STATUS        = NO_RULE_APPROVED
PRODUCT_CANDIDATE_STATUS          = NO_CANDIDATE
REAL_WORLD_DECISION_UTILITY       = PENDING
```
