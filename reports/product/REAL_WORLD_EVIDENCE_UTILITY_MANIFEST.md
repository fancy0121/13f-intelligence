# REAL-WORLD EVIDENCE UTILITY MANIFEST (v0.5)

> Generated: 2026-08-26 | Prospective observation infrastructure delivered

## Final Status

```text
PREDICTIVE_RESEARCH_STOP_RULE              = TRIGGERED
PREDICTIVE_PRODUCT_SIGNAL_STATUS           = DISABLED
EVIDENCE_PRODUCT_STATUS                    = CANDIDATE_READY_FOR_REAL_USE
REAL_USE_OBSERVATION_INFRASTRUCTURE_STATUS = DELIVERED
REAL_WORLD_EVIDENCE_UTILITY                = INSUFFICIENT_OBSERVATION
REAL_WORLD_DECISION_UTILITY                = PENDING
```

## Repository

- Baseline HEAD: `dcfa839` (v0.4 final, 148 tests)
- v0.5 real-use protocol freeze SHA: `97103bb`
  (`V0_5_REAL_USE_PROTOCOL_FREEZE_VERSION=v0.5`)
- Final HEAD: the commit containing this manifest (see git log)
- Worktree: clean after final commit

## Observation State (fact, not judgment)

- Real-use episodes recorded: **0** (raw), **0** valid.
- No synthetic episodes were generated; no pre-protocol usage exists.
- `REAL_WORLD_EVIDENCE_UTILITY=INSUFFICIENT_OBSERVATION` until 20 VALID
  episodes accumulate. Infrastructure completion does NOT imply support.

## Infrastructure Delivered

- Protocol: docs/real_world_evidence_utility_protocol_v0.5.md
- Episode schema + validity rules (PENDING -> VALID /
  INVALID_NO_PRE_USE_CAPTURE / INVALID_SYNTHETIC_TASK /
  INVALID_PRODUCT_ERROR / INVALID_DUPLICATE / INVALID_OTHER)
- Local append-only JSONL logger (`data/real_use/`, gitignored) + product
  error log
- Pre-use / post-use capture workflows (CLI + Observation page)
- Utility aggregation + deterministic threshold verdicts
  (SUPPORTED / MIXED / LOW_INCREMENTAL_VALUE / INSUFFICIENT_OBSERVATION)
- Misuse monitoring (NONE/LOW/MODERATE/HIGH; user vs product-induced),
  version tracking, CSV/JSON export
- Tests: 15 observation tests + full regression
- Status report: reports/product/real_use_observation_status.md

## Prior States Preserved

- v0.2.1 Broad unlock NO; v0.2.2 semantic delivered; v0.3 stop triggered;
  v0.4 evidence product candidate.

## Next Step (human, not engineering)

A real user actually uses the product and records episodes. Only correctness,
transparency, misuse-inducing design, or core usability blockers permit a
correction cycle. No further product features are added.

