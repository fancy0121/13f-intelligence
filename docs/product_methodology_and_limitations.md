# Product Methodology and Limitations

## Data source

SEC Form 13F (via the system's own ingestion and validation pipeline). 13F
discloses REPORTED LONG positions of institutional investment managers.

## What is shown

Reported long institutional positions: shares, reported values, portfolio
weights, and deterministic position-change facts (NEW/ADD/REDUCE/EXIT),
repeated reported activity, filing freshness, amendments, and identity/data
quality.

## Delays

Report period and filing date are separate facts and always shown together.
13F filings have an up-to-45-day delay; the data is never real-time
positions.

## Limitations

- Short positions are not disclosed.
- Full hedge / derivative / swap / futures context is unavailable.
- Exact transaction dates and cost basis are unknown.
- Confidential treatment can hide holdings; "not disclosed" is not "not held".
- Amendments change the latest effective state; the source chain is kept.
- Some filers are stale or historically incomplete.
- Security-resolution gaps exist (unresolved/ambiguous/conflict); they are
  shown, never guessed.

## Historical research result (frozen)

- 2Q/3Q persistence improved descriptive structural stability in the research
  layer.
- The frozen v0.3 outcome validation did NOT show incremental economic
  outcome from 2Q or 3Q persistence.
- The predictive research stop rule is TRIGGERED.
- Therefore the product presents evidence, not prediction. Simple
  institutional activity counts remain useful as descriptive baseline facts
  (this is not a claim that they are predictive).

