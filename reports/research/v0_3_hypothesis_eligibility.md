# v0.3 Operating Equity Hypothesis Eligibility (v0.2.2)

> Generated: 2026-08-24 (outcome-blind; POST_RESOLUTION_DIAGNOSTIC / PRE_OUTCOME)
> Protocol: research/security_semantic_audit_protocol_v0.2.2.md (frozen)

## 1. Question

Is there sufficient outcome-free factual basis to propose a NEW, narrower
operating-equity-specific hypothesis (potential v0.3)? This is a hypothesis
ELIGIBILITY audit, not an outcome experiment.

## 2. Core Facts (pre-outcome)

### Universe composition (observation level, O0)

- OPERATING_COMMON_EQUITY 68.5%, OPERATING_ADR 4.7%, OPERATING_OTHER_EQUITY
  0.5% -> Operating total **73.7%** (171,714 obs)
- ETF 14.7%, MUTUAL_OR_POOLED_FUND 1.6%, CLOSED_END_FUND 0.6% -> Pooled
  total **16.9%** (39,497 obs)
- UNKNOWN 4.1%, REIT/special 3.0%, non-equity 1.7%, other small

### Behavioral structure (Operating vs Pooled, pre-outcome)

| Descriptor | Operating | Pooled | abs diff |
|---|---|---|---|
| NEW rate | 21.2% | 30.4% | 9.2pp |
| ADD rate | 34.2% | 22.9% | 11.2pp |
| REDUCE rate | 30.4% | 22.0% | 8.3pp |
| EXIT rate | 9.8% | 20.9% | 11.1pp |
| Turnover proxy | 0.325 | 0.533 | 0.208 |
| Persistence 2Q rate | 29.0% | 21.8% | 7.2pp |
| Persistence 3Q rate | 9.3% | 4.7% | 4.6pp |
| Weight mean | 0.158% | 0.016% | 10x |
| Managers per security (mean) | 4.48 | 1.52 | 3.0 |
| Reversal rate | 55.7% | 67.7% | 12.0pp |

- `MANAGER_COMPOSITION_CONFOUNDED=False`: within-manager operating-vs-pooled
  differences are mixed; the aggregate gap is NOT driven by a few managers.
- `TIME_COMPOSITION_SENSITIVE=True`: the quarterly positive-rate gap ranges
  -5.1pp..+8.7pp; structural descriptors (turnover, persistence, size,
  participation) are stable aggregates.
- **Persistence finding (§27)**: pooled vehicles are LESS persistent than
  operating equities. A1's stability is therefore NOT a pooled-universe
  artifact; operating equities themselves exhibit the same/higher persistence
  pattern.

### Natural resolution (operating-only audit view, resolver unchanged)

- Operating securities: 6,509; resolver VERIFIED 4,699 (72.2%)
- Observation coverage: O0 84.88%, O1_2Q 86.17%, O1_3Q 86.62%
- Per split (O0): dev 79.26%, time 88.38%, manager 85.73%, security 79.56%,
  combined 89.36%
- This is higher than the Broad 69.97% but STILL below the frozen 90%
  threshold; v0.3 would need its own coverage policy (or missingness bounds).

### Missingness (within Operating Equity audit set)

- `OPERATING_EQUITY_MISSINGNESS_STATUS=MODERATE_CONCERN` (15.12% unmapped;
  25,963 / 171,714)
- Direction gap small (positive 14.1%, negative 16.6%); dev/security holdout
  ~20%; earlier quarters higher missing (declining 22.8% -> 8.1%)

### Failure taxonomy (Broad universe)

6,766 non-VERIFIED securities decomposed: FUND_OR_ETF_IDENTITY_PATH_MISSING
3,322 (49.1%), UNKNOWN_REASON 1,226 (18.1%), NAME_OR_ENTITY_CONFLICT 681
(10.1%), DELISTED_OR_TERMINATED 679 (10.0%), NON_EQUITY 442 (6.5%),
OPENFIGI_MULTI_MATCH 246 (3.6%), SEC_CORROBORATION_MISSING 138 (2.0%),
ADR_OR_ORDINARY_AMBIGUITY 32 (0.5%).

### Variant mapping bias decomposition

- Overall coverage: O0 69.97% / O1_2Q 73.84% / O1_3Q 77.35%
- Within OPERATING_COMMON_EQUITY: O0 85.43% / O1_2Q 86.73% / O1_3Q 87.25%
  (gap <=1.8pp) -> the O1/O2 advantage is **mostly a security-type
  composition effect**, not within-type mapping bias.

## 3. J1-J5 Assessment

### J1 — Semantic coherence: PASS

Operating company equity (ownership claim on an operating business) and
pooled vehicles (wrapper products; ETF/fund/CEF) are economically distinct
structures by definition and by SEC instrument type.

### J2 — Observable behavioral distinction: PASS (with caveat)

Non-trivial, pre-outcome differences exist on structural descriptors:
turnover (0.53 vs 0.33), persistence (2Q 29.0% vs 21.8%; 3Q 9.3% vs 4.7%),
position size (10x), manager participation (3x), reversal rate (67.7% vs
55.7%). Not manager-composition-confounded. Caveat: the quarterly
positive-rate gap is time-sensitive; the distinction rests on the stable
structural descriptors, not on a single quarter.

### J3 — Not merely mapping convenience: PASS

The hypothesis is motivated by economic semantics and observable behavior,
not by resolver coverage. The coverage difference (operating 84.9% vs broad
70.0%) is a secondary technical benefit, not the justification. (And even
operating coverage is below the frozen 90% broad threshold, so "easier to
map" cannot be the argument.)

### J4 — Selection audit acceptable: PASS (with documented shifts)

Manager deltas are small except manager 26 (broad 36.4% -> operating 28.4%,
-8.0pp) - the ETF-heavy manager - which is expected for an operating-only
set. Quarter deltas <0.5pp; direction deltas small. Missingness within
operating is MODERATE (15.1%) and must be handled by missingness bounds in a
v0.3 preregistration. No unacceptable distortion.

### J5 — Research-question coherence: PASS

Institutional stock-selection evidence concerns operating companies; pooled
vehicles are a different research object (fund allocation / wrapper trading).
An operating-equity hypothesis is directly aligned with the project goal.

## 4. Verdict

```text
V0_3_OPERATING_EQUITY_HYPOTHESIS=JUSTIFIED_FOR_NEW_PREREGISTRATION
```

This does NOT unlock anything. Per protocol §47 this round stops. A v0.3
preregistration, if the external reviewer approves, must:

- be a fresh, independent, outcome-blind protocol (not a continuation);
- pre-register its own coverage/eligibility policy for operating types
  (current natural coverage 84.9%; unresolved ~15%);
- include simple partial-identification bounds
  (recommendation below) for the ~15% unresolved operating observations;
- re-check the time-sensitive positive-rate gap and manager-26 composition
  shift;
- not reuse any v0.2.1 frozen O0/O1/O2 as-is without re-preregistration.

## 5. Partial Identification Recommendation

`PARTIAL_IDENTIFICATION=RECOMMENDED` - with ~15% unresolved operating
observations (MODERATE_CONCERN), a future v0.3 outcome should report
worst/best-case bounds (and optionally a simple exclusion-restriction
sensitivity) alongside the main estimate. No bounds are implemented or run
in this round.

