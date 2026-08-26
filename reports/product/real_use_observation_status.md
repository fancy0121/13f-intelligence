# Real-Use Observation Status (v0.5)

> Generated: 2026-08-26T10:46:08.927964+00:00

VALID episodes: 0 / target 20
Raw episodes: 0 | unique targets: 0 | clustered effective: 0

REAL_WORLD_EVIDENCE_UTILITY=INSUFFICIENT_OBSERVATION

## Utility metrics (valid episodes only)

| metric | value |
|---|---|
| incremental_information_rate | 0.0 |
| research_path_change_rate | 0.0 |
| no_incremental_information_rate | 0.0 |
| contradiction_exposure_rate | 0.0 |
| quality_risk_discovery_rate | 0.0 |
| stale_assumption_corrected_rate | 0.0 |
| portfolio_share | 0.0 |

## Scenario / familiarity / effort / misuse

- scenario: {'security': 0, 'manager': 0, 'portfolio': 0}
- familiarity: {'familiar': 0, 'unfamiliar': 0, 'UNKNOWN': 0}
- effort buckets: {}
- misuse risk: {'NONE': 0, 'LOW': 0, 'MODERATE': 0, 'HIGH': 0, 'UNKNOWN': 0}
- product-design-induced misuse: 0
- product versions: {}

## Observation mix

- security >=8: OBSERVATION_MIX_INCOMPLETE
- manager >=4: OBSERVATION_MIX_INCOMPLETE
- portfolio <=40%: OK
- unfamiliar >=5: OBSERVATION_MIX_INCOMPLETE

When fewer than 20 VALID episodes exist, no real-world utility conclusion is drawn.
