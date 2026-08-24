# FINAL SECURITY RESOLUTION MANIFEST (v0.2.1)

> Generated: 2026-08-24 (single final delivery)

## Final Status

```text
SECURITY_RESOLUTION_HARNESS_STATUS = DELIVERED
OUTCOME_UNLOCK                    = NO
OUTCOME_VALIDATION_STATUS         = PARTIAL_COVERAGE_GATES_FAIL
PRODUCT_METHODOLOGY_STATUS        = NO_RULE_APPROVED
PRODUCT_CANDIDATE_STATUS          = NO_CANDIDATE
REAL_WORLD_DECISION_UTILITY       = PENDING
```

The blanket `NO_APPROVED_PROVIDER` status is retired: identity mapping
(OpenFIGI + SEC) and price capability (Yahoo Chart) are both approved. The
outcome remains locked because the frozen coverage / bias gates FAIL, not
because providers are missing.

## Repository

- Baseline HEAD: `32a782c2285644cf141577af7be10033353a1a08`
- Resolution protocol freeze SHA: `4a53ab1` (`SECURITY_RESOLUTION_PROTOCOL_FREEZE_VERSION=v0.2.1`)
- Final HEAD: the commit containing this manifest (see `git log`)
- Worktree: clean after final commit

## Gates

| Gate | Result |
|---|---|
| R1 Protocol Integrity | PASS (frozen before pilot) |
| R2 Provider Truth | PASS (per-function matrix; OpenFIGI CUSIP corrected) |
| R3 False Mapping | PASS (0 known false VERIFIED in golden audit) |
| R4 Historical Identity | PASS (rename/ADR/share-class; class-share price fix applied) |
| R5 Coverage | **FAIL** (O0 69.99% / O1_2Q 73.86% / O1_3Q 77.36%; frozen min 90%) |
| R6 Mapping Bias | **FAIL** (dev vs holdout diff >5pp; VARIANT_MAPPING_BIAS) |
| R7 Outcome Unlock | **NO** |

## Key Numbers

- Eligible universe securities: 12,794 (R0 12,794 / R1 9,690 / R2 6,528)
- VERIFIED securities: 6,028 (47.1%): VERIFIED_MULTI_SOURCE 3,521,
  VERIFIED_EXACT 2,507
- AMBIGUOUS 743 / CONFLICT 216 / NON_EQUITY_OR_UNSUPPORTED 442 /
  UNRESOLVED 5,365
- Manual review queue: 959 rows (AMBIGUOUS/CONFLICT), impacting 7,099
  observations (3.0% of O0); the 5,375 UNRESOLVED are reported as counts, not
  dumped on the user.
- Observation coverage (frozen denominator): O0 69.97%, O1_2Q 73.84%,
  O1_3Q 77.35%; per-split worst 61.97% (O0 H0_dev).

## Precise Blocker (why OUTCOME_UNLOCK=NO)

1. **Observation coverage below frozen 90%**: ~25% of eligible observations
   are fund/ETF CUSIPs that cannot be VERIFIED under frozen Rule C because
   SEC company-ticker files do not contain most fund tickers, and 13F
   title_of_class is truncated by filers; plus a tail of delisted / foreign /
   no-US-venue common stocks.
2. **Differential coverage**: dev vs manager/combined holdouts differ by up to
   ~17pp (frozen max 5pp).
3. **Variant mapping bias**: O1_3Q resolves 7.4pp better than O0; persistence
   variants are common-stock-heavy, so an unbiased O0-vs-O1 comparison is not
   possible under current resolution rules.

## Minimal Path to Resolution (not a promise)

- `NEXT_PROTOCOL_CANDIDATE` (required): a fund-verification rule that does not
  depend on SEC per-fund tickers (e.g., OpenFIGI exact CUSIP + independent
  fund-name corroboration, or a curated Tier-4 fund table for the top-N
  high-observation funds), plus a re-evaluation of the 90% threshold against
  the non-fund equity universe.
- Manual review of the 964 AMBIGUOUS/CONFLICT rows would recover at most 7,106
  observations (3.0%) and is therefore NOT sufficient alone.
