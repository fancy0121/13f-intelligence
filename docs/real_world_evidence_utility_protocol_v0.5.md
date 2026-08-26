# Real-World Evidence Utility Observation Protocol v0.5 (PRE-REGISTERED)

> Frozen BEFORE any formal real-use episode is counted. Changes require a new
> protocol version. This round builds observation INFRASTRUCTURE only; no
> fake episodes, no synthetic users.

## 1. Objective

Prospectively observe whether the v0.4 Evidence Product provides independent,
incremental, actionable information value in real investment-research
processes. v0.5 does NOT validate alpha, future returns, or stock-picking
performance. Predictive research remains stopped.

## 2. Episode Definition (REAL_USE_EPISODE)

A real investment-research task = one episode. An episode MUST record
pre-use state BEFORE product exposure, then product exposure, then post-use
outcomes. Pre-use capture precedes product findings; otherwise the episode
is `INVALID_FOR_INCREMENTAL_UTILITY` and excluded from the core sample.

## 3. Episode Schema (frozen)

episode_id, episode_cluster_id, created_at, updated_at, target_type
(security|manager|portfolio), target_id, target_label, is_portfolio_target,
familiarity_class (familiar|unfamiliar|UNKNOWN), research_question,
pre_use_knowledge, pre_use_assumptions, pre_use_uncertainties,
planned_next_step, baseline_method, product_views_used, product_version,
new_fact_found, contradicting_fact_found, stale_assumption_corrected,
quality_risk_discovered, research_path_changed, research_time_saved,
no_incremental_information, estimated_manual_effort_bucket,
misuse_risk, misuse_type, product_design_issue, post_use_next_step,
notes, episode_validity, invalid_reason.

No unnecessary sensitive data. Local first; never uploaded.

## 4. Validity Rules (frozen)

- VALID: pre-use captured before post-use; not synthetic; no product error;
  not duplicate.
- INVALID_NO_PRE_USE_CAPTURE: no pre-use state saved before exposure.
- INVALID_SYNTHETIC_TASK: marked synthetic (e.g., staff/test/demo).
- INVALID_PRODUCT_ERROR: a recorded product factual error invalidated the
  episode (see product error log).
- INVALID_DUPLICATE: same episode_cluster_id already has a completed valid
  episode within the clustering rule (repeated same-target queries in the
  same session cluster to avoid pseudo-replication).
- INVALID_OTHER.

Only VALID episodes enter utility analysis.

## 5. Post-use Outcome Taxonomy (frozen)

Flags (0/1, user-confirmed): NEW_FACT_FOUND, CONTRADICTING_FACT_FOUND,
STALE_ASSUMPTION_CORRECTED, QUALITY_RISK_DISCOVERED, RESEARCH_PATH_CHANGED,
RESEARCH_TIME_SAVED, NO_INCREMENTAL_INFORMATION. `NO_INCREMENTAL_INFORMATION`
is legal. No forced positive utility.

Subjective flags (pre_use_knowledge, contradiction, path_changed,
incremental_information, misuse) are NEVER auto-populated by code; they come
from user confirmation or episode notes.

## 6. Misuse Taxonomy (frozen)

mISUSE_RISK in {NONE, LOW, MODERATE, HIGH}.
- USER_MISINTERPRETATION: product expressed limits, user over-read.
- PRODUCT_DESIGN_INDUCED: UI/copy induced confirmation / predictive
  inference / stale-data neglect / ranking mentality -> product defect,
  fix allowed.

## 7. Observation Mix (frozen, soft targets)

First 20 VALID episodes aim for: Security research >=8; Manager research >=4;
My Portfolio <=8 (<=40%); unfamiliar target >=5. If natural use cannot reach
mix -> `OBSERVATION_MIX_INCOMPLETE`, continue observing, do not fabricate.

## 8. Duplicate Handling (frozen)

Repeated queries of the same target are recorded with episode_cluster_id.
Report raw episode count, unique target count, clustered effective count.

## 9. Utility Metrics (frozen; no composite score)

Valid Episodes; Unique Targets; Incremental Information Rate (>=1 of
NEW_FACT/CONTRADICTING/STALE_CORRECTED/QUALITY_RISK); Research Path Change
Rate; No Incremental Information Rate; Contradiction Exposure Rate (per
pre-use expectation, user-confirmed); Quality Risk Discovery Rate; Estimated
Manual Effort buckets; Misuse Risk Rate. No "utility score" is computed.

## 10. Baseline Comparison (frozen, light)

Pre-use records planned alternative: manual SEC search / web / prior
knowledge / external dashboard / not planned. Post-use records
estimated_manual_effort_bucket (<5, 5-15, 15-30, >30 min, UNKNOWN). No false
minute precision.

## 11. Threshold Governance (frozen; deterministic at 20 VALID episodes)

- SUPPORTED: Incremental Information Rate >=50% AND >=20% episodes have at
  least one of CONTRADICTING/STALE_CORRECTED/QUALITY_RISK AND
  NO_INCREMENTAL <=50% AND PRODUCT_DESIGN_INDUCED misuse <=10% AND no severe
  factual integrity defect.
- LOW_INCREMENTAL_VALUE: NO_INCREMENTAL >=70% AND Path Change <15% AND
  contradiction/stale/quality discovery rare.
- MIXED: valid sample = 20 and neither SUPPORTED nor LOW.
- INSUFFICIENT_OBSERVATION: valid episodes <20.

Thresholds are governance rules, not natural law. No threshold fishing;
revision proposals go to NEXT_PROTOCOL_REVISION_CANDIDATE only.

## 12. Early Review (frozen)

At 5 and 10 VALID episodes, run SAFETY/PRODUCT-DEFECT review only (factual
errors, UI confusion, misuse induced by design, logging burden, missing
quality display). Do NOT adjust metrics/ranking/selection/language for
utility.

## 13. Product Fix Policy (frozen)

Allowed during observation: correctness defect, transparency defect,
usability defect (scenario blocked), misuse-inducing design. Fixes are
logged, versioned, date-effective (`product_version`). Forbidden: adding
predictive signal/ranking/recommendation/AI insight; changing outcome
taxonomy; removing NO_INCREMENTAL; changing observation mix or success
criteria; cherry-picking securities; making the home page "brighter".

## 14. Stop / Continue (frozen)

First window = 20 VALID episodes. Then report one of SUPPORTED / MIXED /
LOW_INCREMENTAL_VALUE / INSUFFICIENT_OBSERVATION. Decision quality is NOT
decision agreement: a user may keep a position after seeing exits; that is
not utility failure.

## 15. Product Errors

Record error_id, episode_id, affected fact, severity, root cause, fix SHA,
affected prior episodes. Severe factual errors re-evaluate related episode
validity.

## 16. Anecdotal Predictive Observations

User anecdotes like "that pattern went up later" are recorded as
`ANECDOTAL_PREDICTIVE_OBSERVATION_NOT_ACTIONABLE`; predictive research stays
stopped.

## 17. Infrastructure Only

This round delivers: protocol, episode schema, local logger/storage
(append-only JSONL), pre/post workflows, validity, aggregation/reporting,
misuse monitoring, version tracking, tests, status report, manifest, final
report. No new investment features. No AI summary. No telemetry/cloud.

## 18. Final Status (frozen semantics)

```text
REAL_USE_OBSERVATION_INFRASTRUCTURE_STATUS = DELIVERED
REAL_WORLD_EVIDENCE_UTILITY               = PENDING_OBSERVATION (0 valid)
                                             | INSUFFICIENT_OBSERVATION (<20)
                                             | SUPPORTED | MIXED | LOW_INCREMENTAL_VALUE
REAL_WORLD_DECISION_UTILITY               = PENDING
```

## 19. Freeze Marker

`V0_5_REAL_USE_PROTOCOL_FREEZE_VERSION=v0.5`

