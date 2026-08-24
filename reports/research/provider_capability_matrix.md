# Provider Capability Matrix (Security Resolution & Outcome v0.2.1)

> Status: COMPLETED (2026-08-24) — Gate R2 evidence
> Principle: capabilities are evaluated **per function**, not with one
> blanket APPROVED/NOT-APPROVED verdict. The previous blanket
> `NO_APPROVED_PROVIDER` is retired.

## 1. Matrix

| Provider | Identity Mapping | Historical Price | Benchmark Data | Corporate Actions | Historical Symbol Continuity |
|---|---|---|---|---|---|
| SEC company_tickers / company_tickers_exchange | PASS (issuer/CIK/ticker; current only; share-class ambiguous) | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED | PARTIAL (current ticker only; no former tickers) |
| SEC 13F filing issuer metadata (FACT layer) | PASS (issuer identity corroboration for every CUSIP) | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED | PARTIAL (no ticker at all) |
| OpenFIGI mapping (ID_CUSIP / ID_CUSIP_8_CHR / ID_ISIN) | PASS (unique shareClassFIGI + US ticker; see openfigi_identifier_audit.md) | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED | FAIL for historical symbols (current ticker only) |
| Yahoo Search (CUSIP->symbol) | **FAIL / NON_TRUSTED** (foreign listings win; no provenance) | n/a | n/a | n/a | n/a |
| Yahoo Chart API (v8) | NOT_EVALUATED (not a mapping source) | **PASS** | **PASS** (^GSPC) | **PASS** (adjusted close + splits + dividends events) | **PASS for provider continuity** (see §5) |
| Stooq CSV | FAIL (noindex HTML) | FAIL | n/a | n/a | n/a |

## 2. Approved Providers (per capability)

- `APPROVED_MAPPING_PROVIDER = OpenFIGI` (identity, CUSIP -> US instrument)
  with SEC issuer corroboration (SEC ticker files and/or 13F filing issuer
  metadata).
- `APPROVED_PRICE_PROVIDER = Yahoo Chart API` (historical daily prices,
  adjusted close, splits, benchmark ^GSPC, 404 for unknown/delisted).
- `NON_TRUSTED_MAPPING_SOURCE = Yahoo Search` (never enters VERIFIED mapping).

## 3. Identity Mapping — SEC

Live evidence (2026-08-24, official files cached at
`data/resolution_cache/company_tickers*.json`, sha256 recorded):

- `company_tickers.json`: 10,403 CIK->ticker->title records.
- `company_tickers_exchange.json`: 10,403 rows (cik, name, ticker, exchange).
- Pilot issuer corroboration (normalized title match):
  AMZN, GOOGL/GOOG (Alphabet, same CIK 1652044 - class must come from CUSIP),
  META, MSFT, V, TSM, AVGO, UNH, XYZ, PDD, UBER, SNOW, CRM, DASH, CPNG all
  matched. NVDA/DHR/COF require abbreviation-normalized matching (CORP vs
  CORPORATION, FINL vs FINANCIAL) - handled deterministically in the resolver.
- SEC states ticker association is not guaranteed complete; SEC ticker is
  evidence, not an override on conflict.

## 4. Identity Mapping — OpenFIGI

See `openfigi_identifier_audit.md`. Summary: PASS for US CUSIPs; multi-venue
responses collapse to a single distinct US ticker via US exchange-code filter;
unique `shareClassFIGI` per CUSIP; `securityType` distinguishes ADR vs Common
Stock; non-US CUSIP (G3643J108) unsupported without ISIN.

## 5. Historical Symbol Continuity — Yahoo Chart (provider-continuity pilot)

Live evidence (2026-08-24, period 2022-01-01..2026-05-28, 1d bars):

| Symbol | Bars | First | Last | adjclose | Splits | Note |
|---|---|---|---|---|---|---|
| GOOGL | 1104 | 2022-01-03 | 2026-05-28 | yes | 1 | continuous |
| GOOG | 1104 | 2022-01-03 | 2026-05-28 | yes | 1 | continuous |
| TSM | 1104 | 2022-01-03 | 2026-05-28 | yes | 0 | continuous |
| XYZ (Block) | 1104 | 2022-01-03 | 2026-05-28 | yes | 0 | **rename SQ->XYZ covered by current symbol** |
| SQ (old) | - | - | - | - | - | **HTTP 404** (dead ticker) |
| PDD | 1104 | 2022-01-03 | 2026-05-28 | yes | 0 | continuous |
| META | 1104 | 2022-01-03 | 2026-05-28 | yes | 0 | **rename FB->META covered by current symbol** |
| FB (old) | 232 | 2025-06-26 | 2026-05-28 | yes | 0 | **ticker reused by another issuer - do NOT use old tickers blindly** |
| AMZN | 1104 | 2022-01-03 | 2026-05-28 | yes | 1 | continuous |
| ^GSPC | 1104 | 2022-01-03 | 2026-05-28 | yes | 0 | benchmark |

Conclusion:

- Current symbols with full history back to at least 2022-01-01 provide
  continuous identity across renames for the tested cases (Block, Meta).
- Old tickers are unreliable (FB reused; SQ dead). Historical observations
  must therefore use **current-symbol continuity** (verified start date <=
  observation info date) or **curated historical symbols** with
  valid_from/valid_to.
- `PROVIDER_CONTINUITY_VERIFIED` is granted per security when (1) an
  independent identity source (OpenFIGI + SEC issuer) proves the same share
  class, (2) Yahoo chart for the current symbol returns bars covering the
  observation window, and (3) no corporate action breaks identity (splits are
  handled by adjusted close; no security-level identity change observed).

## 6. Retired Blanket Verdict

`NO_APPROVED_PROVIDER` is no longer a valid overall status. The previous
conclusion conflated a mapping-provider gap with a price-provider gap. Both
capabilities are now available (OpenFIGI+SEC for identity, Yahoo for price),
so the outcome pipeline can be unlocked mechanically if the resolution gates
pass.

