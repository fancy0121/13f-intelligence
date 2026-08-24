# Market Data Provider Audit (Outcome v0.2)

> Generated: 2026-08-24

## Candidates evaluated

| Provider | Free/No key | Prices | Adjusted close | Splits/Dividends | Benchmark | CUSIP→symbol | Verdict |
|---|---|---|---|---|---|---|---|
| Yahoo Finance chart API | Yes | PASS | PASS | PASS (4:1 AAPL split fixture) | PASS (^GSPC) | **FAIL** | REJECT for symbol identity |
| Yahoo search (CUSIP→symbol) | Yes | n/a | n/a | n/a | n/a | **FAIL** (foreign listings first) | REJECT |
| OpenFIGI anonymous mapping | Yes | n/a | n/a | n/a | n/a | FAIL (CUSIP/ISIN unsupported) | REJECT |
| Stooq CSV | Yes | BLOCKED (noindex HTML) | n/a | n/a | n/a | n/a | REJECT |

## Yahoo chart API — verified capabilities

- Historical daily prices: PASS (AAPL 2021-01 window, 19 bars returned).
- Adjusted close: PASS (`indicators.adjclose` present).
- Split handling: PASS (`events.splits` with 4:1 ratio for AAPL 2020-08-31).
- Dividend handling: `events=div%2Csplit` supported; adjusted close is total-return-compatible (dividends reinvested).
- Benchmark: PASS (`^GSPC` returns aligned bars).
- Delisted / unknown symbol: PASS (404 → OUTCOME_UNRESOLVED_SECURITY).

## Symbol identity resolution — FAIL

- CUSIP 02079K305 (Alphabet CL A / GOOGL) resolved to `1GOOGL.MI` (Milan) instead of US-listed GOOGL.
- CUSIP 874039100 (TSMC ADR / TSM) resolved to `0LCV.IL` (London).
- CUSIP 852234103 (Block Inc) resolved to `XYZ`; the historical symbol was SQ (ticker changed 2026) — symbol-history cannot be reliably reconstructed from search.
- Direct ticker search returns the correct US listing, but CUSIP→symbol via search is not auditable (no provenance; foreign listings win).
- OpenFIGI anonymous mapping returns `Invalid value for idType` for CUSIP and ISIN; only TICKER works (cannot invert CUSIP→symbol).

## Licensing / usage limitations

- Yahoo Finance chart/search endpoints are unofficial; no documented license for bulk automated retrieval. Research-only use, local caching, no redistribution.
- OpenFIGI anonymous tier: rate-limited; no CUSIP support observed.

## Conclusion

No provider passes the full acceptance gate (symbol identity required).

`FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER`