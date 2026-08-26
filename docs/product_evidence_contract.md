# Product Evidence Contract

> Frozen 2026-08-26 (v0.4). Every product metric must be auditable.

Conventions:

- FACT: read directly from the SQLite FACT layer.
- DERIVED FACT: deterministic function of FACT (documented formula).
- Identity quality: from the frozen v0.2.1 resolution artifact
  (`reports/research/security_resolution_master.csv`) and the v0.2.2 semantic
  classification (`reports/research/security_semantic_classification.csv`).
- Missing data behavior: never filled by guessing; show `INSUFFICIENT_DATA`
  or the actual absent count.
- Amendment behavior: latest effective filing wins; amendment chain preserved
  via filings.amends_filing_id.
- Stale behavior: explicit `STALE_DATA` when the latest available filing is
  older than the expected cadence (45-day delay is normal; >180 days = stale).

## Metrics

### holder_entity_count (DERIVED FACT)
- Source: position_changes (latest report period, put_call=''), distinct
  manager_id.
- Formula: COUNT(DISTINCT manager_id).
- Identity requirement: none (entity count includes all tracked entities).

### verified_independent_manager_count (DERIVED FACT)
- Source: position_changes joined managers; independence per manager
  governance (config/managers.csv validation_status, no family merging unless
  explicitly scoped).
- Formula: COUNT(DISTINCT manager_id) among independence-confirmed managers;
  `UNKNOWN` when independence cannot be confirmed.
- Note: holder_entity_count and this number are reported separately.

### independent_add_manager_count / independent_reduce_manager_count /
### independent_new_manager_count / independent_exit_manager_count (DERIVED FACT)
- Source: position_changes (change_type in NEW/ADD/REDUCE/EXIT, put_call='',
  latest report period), distinct verified-independent manager_id.
- Missing behavior: absent count shown as 0 (never hidden).

### repeated_add_manager_count / repeated_reduce_manager_count (DERIVED FACT)
- Source: position_changes across consecutive report periods per
  (manager_id, security_id).
- Definition: manager reported the same direction in >= 2 consecutive
  reporting periods. Missing filing / absent quarter BREAKS the run (no gap
  crossing).
- Identity: verified-independent managers only; else UNKNOWN.

### latest_report_period / latest_filing_date / days_since_filing (FACT/DERIVED)
- Source: filings (effective latest per manager+period; amendment-aware).
- Display: report period AND filing date AND information age always together.

### stale_flag / amendment_flag / unresolved_count / conflict_count (FACT/DERIVED)
- stale_flag: latest filing older than 180 days from expected reporting.
- amendment_flag: filings.is_amendment=1 in the period chain.
- unresolved_count/conflict_count: resolution artifact status counts for the
  shown scope.

### activity_state (DERIVED FACT)
- From independent_add vs independent_reduce counts in latest period:
  MORE_ADDS_THAN_REDUCTIONS / MORE_REDUCTIONS_THAN_ADDS / MIXED_ACTIVITY /
  NO_RECENT_CHANGE / LOW_BREADTH (<2 independent managers with any action) /
  STALE_DATA / INSUFFICIENT_DATA. Counts always displayed alongside.

## Guarantees

- No hidden manager weighting (count = count).
- No hidden security filtering (eligible types and identity exclusions are
  stated on the Activity Explorer).
- No evidence/confidence/consensus score.

