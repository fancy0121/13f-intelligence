# OpenFIGI Identifier Capability Audit

> Status: COMPLETED (2026-08-24) — Gate R2 evidence
> Provider: OpenFIGI anonymous mapping API v3 (`https://api.openfigi.com/v3/mapping`)
> Method: live POST requests, official API, no API key, batched (10 jobs/request)

## 1. Correction of Previous Assumption

The previous provider audit (`reports/research/market_data_provider_audit.md`,
commit 03ca1bc) stated:

> OpenFIGI anonymous mapping returns `Invalid value for idType` for CUSIP and
> ISIN; only TICKER works (cannot invert CUSIP->symbol).

**This is RETRACTED / CORRECTED.** The previous test used the wrong identifier
type string (`CUSIP`). OpenFIGI's official enum for CUSIP lookup is
`ID_CUSIP` (9-character CUSIP) and `ID_CUSIP_8_CHR` (8-character CUSIP); the
official enum for ISIN is `ID_ISIN`. A single failed request with an invalid
enum value does not prove capability absence. This audit re-tests with the
correct enums and records real responses.

## 2. Capability Verified

| Identifier type | Enum | Result |
|---|---|---|
| CUSIP (9-char) | `ID_CUSIP` | PASS - resolves US CUSIPs |
| CUSIP (8-char) | `ID_CUSIP_8_CHR` | PASS - resolves US CUSIPs |
| ISIN | `ID_ISIN` | PASS - resolves US ISINs (sample tested) |

Anonymous tier: no API key required for basic mapping. A free API key only
raises rate limits / batch size; it is not required for correctness.

## 3. Multi-Result Behavior (important)

`ID_CUSIP` for a single US CUSIP returns a **large number of venue records**
(100-280 in the pilot), because the same share class trades on many exchanges
worldwide. All records share:

- the same `shareClassFIGI` (the security-class identity)
- the same `name` and `securityType`
- identical US ticker on US venues; different tickers on foreign venues
  (e.g., AMZN US vs `AMZ` on German venues, `AMZNEUR` etc.)

Therefore:

- **Never take the first result**.
- **Never take the most common ticker**.
- The correct identity key is `shareClassFIGI`; the correct US-market ticker is
  obtained by filtering to US venue exchange codes and requiring a single
  distinct ticker.

## 4. US Exchange Filter

US venue `exchCode` values observed for US-listed equity share classes:
`US, UN, UA, UC, UP, UB, UM, UX, UD, UW, UF` (plus occasional `UQ`, `VL`, `VG`,
`VP`, `VF`, `OC`, `OD`, `VT` for additional venues). After filtering to these
codes, each pilot CUSIP produced **exactly one distinct ticker** (19/20 cases;
`G3643J108` returned 0 results - see section 6).

## 5. Pilot Result Summary (live evidence)

Probed 2026-08-24, `ID_CUSIP` 9-char, US-exchange filter applied:

| CUSIP | shareClassFIGI | US ticker(s) | securityType | name | Previous failure |
|---|---|---|---|---|---|
| 023135106 | BBG001S5PQL7 | AMZN | Common Stock | AMAZON.COM INC | - |
| 02079K305 | BBG009S39JY5 | GOOGL | Common Stock | ALPHABET INC-CL A | FOREIGN_LISTING_ISSUE FIXED |
| 30303M102 | BBG001SQCQC5 | META | Common Stock | META PLATFORMS INC-CLASS A | - |
| 594918104 | BBG001S5TD05 | MSFT | Common Stock | MICROSOFT CORP | - |
| 67066G104 | BBG001S5TZJ6 | NVDA | Common Stock | NVIDIA CORP | - |
| 92826C839 | BBG001SRCFY3 | V | Common Stock | VISA INC-CLASS A SHARES | - |
| 874039100 | BBG001S5WWW4 | TSM | ADR | TAIWAN SEMICONDUCTOR-SP ADR | FOREIGN_LISTING_ISSUE FIXED |
| 11135F101 | BBG00KHY5SY8 | AVGO | Common Stock | BROADCOM INC | - |
| G3643J108 | - | (0 results) | - | - | NEW UNRESOLVED CANDIDATE |
| 91324P102 | BBG001S6WCJ1 | UNH | Common Stock | UNITEDHEALTH GROUP INC | - |
| 852234103 | BBG001TFLWL5 | XYZ | Common Stock | BLOCK INC | SYMBOL_HISTORY (current ticker) |
| 722304102 | BBG00LBLDFH8 | PDD | ADR | PDD HOLDINGS INC | UNRESOLVED FIXED |
| 235851102 | BBG001S5QGT0 | DHR | Common Stock | DANAHER CORP | - |
| 02079K107 | BBG009S3NB21 | GOOG | Common Stock | ALPHABET INC-CL C | - |
| 90353T100 | BBG002B04MW4 | UBER | Common Stock | UBER TECHNOLOGIES INC | - |
| 833445109 | BBG007DHGNK2 | SNOW | Common Stock | SNOWFLAKE INC | - |
| 79466L302 | BBG001SDLP09 | CRM | Common Stock | SALESFORCE INC | - |
| 25809K105 | BBG005D7QCK1 | DASH | Common Stock | DOORDASH INC - A | - |
| 22266T109 | BBG00XMJRPR7 | CPNG | Common Stock | COUPANG INC | - |
| 14040H105 | BBG001S65PV8 | COF | Common Stock | CAPITAL ONE FINANCIAL CORP | - |

Key corrections vs the previous pilot (`outcome_pilot_mapping_coverage.csv`):

- `02079K305` -> US **GOOGL** (previous: `1GOOGL.MI` foreign listing)
- `874039100` -> US **TSM** ADR (previous: `0LCV.IL` foreign listing)
- `722304102` -> US **PDD** ADR (previous: UNRESOLVED)
- `852234103` -> **XYZ** (Block current ticker; historical symbol SQ handled by
  the historical-symbol layer, see `provider_capability_matrix.md` §5)

## 6. Non-US CUSIP Behavior

`G3643J108` (Flutter Entertainment plc, Irish-domiciled CUSIP) returned
**0 results** with `ID_CUSIP` and `ID_CUSIP_8_CHR`. OpenFIGI does not resolve
this international CUSIP without an ISIN (`IE00BWT6H894` - not present in the
FACT layer). Fallback: SEC company-ticker corroboration (Rule B) or
`UNRESOLVED`. This case is intentionally kept as an honesty test (a CUSIP with
no obvious result must NOT be shortcut).

## 7. Rate Limits / Robustness

- Batch size: 10 jobs per request works on anonymous tier.
- Observed `HTTP 429 Too Many Requests` when issuing rapid sequential
  requests. Mitigation: throttle (>= 0.25s between requests), retry with
  exponential backoff on 429/5xx, and persist a local cache
  (`data/resolution_cache/openfigi/`, gitignored) keyed by idType+idValue with
  retrieval timestamp and raw response.
- The audit deliberately did not hammer the API; all evidence was collected
  with short sleeps and is reproducible from the cached responses.

## 8. Fields to Preserve (per resolved record)

`idType`, `idValue`, `figi`, `compositeFIGI`, `shareClassFIGI`, `ticker`,
`exchCode`, `securityType`, `marketSector`, `name`, `securityDescription`,
response count, retrieval date.

## 9. Verdict

OpenFIGI anonymous **supports CUSIP and ISIN lookup** and is a valid Tier-2
identity source (mapping). It provides current symbols only; historical symbol
continuity must be verified separately (provider-continuity / curated
historical symbols). See `provider_capability_matrix.md`.

