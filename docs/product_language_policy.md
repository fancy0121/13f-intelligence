# Product Language Policy

> Frozen 2026-08-26 (v0.4). Applies to the product path: `src/thirteenf/product/`,
> `app/`, `docs/product_*`, product reports. Research documents may retain
> historical text.

## Allowed

- reported, holding, held, shares, value, portfolio weight
- increased, reduced, initiated, exited, unchanged
- repeated, persistent reported activity
- independent manager count, holder entity count, breadth
- mixed, stale, unresolved, ambiguous, conflict, amended, incomplete
- evidence, fact, derived fact, data quality, filing date, report period
- days since filing, information age
- more adds than reductions, more reductions than adds

## Forbidden (product path)

- buy, sell, hold (as recommendation), bullish, bearish
- conviction, strong conviction, high confidence
- opportunity, likely outperform, alpha, predictive
- smart money, smart-money signal, smart-money picks
- supportive thesis, contrary thesis, thesis supported
- signal (as prediction), score, ranking-as-recommendation
- top ideas, best opportunities, strongest names, hottest names

These words may appear ONLY in methodology/limitations documents when
explaining why they are not used.

## Enforcement

- Product modules and UI must pass the predictive-residue scan
  (reports/product/predictive_residue_audit.md).
- New product code failing the scan is rejected.

