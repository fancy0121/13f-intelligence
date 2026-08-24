# Outcome Mapping Coverage (Outcome v0.2)

> Generated: 2026-08-24

## Pilot (top-20 securities by holder count)

- Total eligible CUSIPs probed: 20
- Price-resolved (some symbol): 19/20
- US-listed, auditable resolution: **~16/20** (3 failures: GOOGL→1GOOGL.MI, TSMC→0LCV.IL, Block→XYZ symbol-history)
- Truly unresolved: 1/20 (PDD 722304102)

## Full-universe projection (unmapped)

- Curated symbol mapping file: empty (`config/outcome_symbols.csv` not populated).
- No CUSIP→symbol mapping is inferred; unresolved securities are `OUTCOME_UNRESOLVED_SECURITY`.

## Mapping bias statement

Because no mapping is used in the formal evaluation, no outcome sample exists; therefore no selection bias can affect conclusions. When a curated mapping is later provided, this report must be regenerated with resolution rate by manager / size / variant.

`OUTCOME_MAPPING_SELECTION_BIAS` status: NOT_APPLICABLE (no resolved sample).