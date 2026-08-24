# Security Resolution Protocol v0.2.1 (PRE-REGISTERED)

> This document is frozen BEFORE any pilot / scale-up / outcome execution.
> After freeze it must not be changed to improve coverage or results.
> Methodology changes require a new `NEXT_PROTOCOL_CANDIDATE`; the frozen
> version is never polluted.
> Scope: Security Identity -> Market Instrument Resolution for the purpose of
> mechanically unlocking the frozen Outcome Validation v0.2 (O0/O1_2Q/O1_3Q).

## 0. Objective

Build a low-false-positive, time-aware, multi-source, auditable
CUSIP -> market instrument resolution layer, and use it to decide
`OUTCOME_UNLOCK=YES/NO` with mechanical pre-registered gates.

False positive > unresolved. Historical mis-assignment > low coverage.
No result is better than a wrong result.

## 1. Canonical Identity vs Market Instrument

Canonical identity stays at the FACT layer: `security_id`, `cusip`, `issuer`,
`class`. A security may map to multiple historical market instruments.
The enrichment record is:

```text
security_id | cusip | figi | composite_figi | share_class_figi | symbol
exchange | security_type | valid_from | valid_to | resolution_status
resolution_sources | retrieved_at
```

`symbol` is a time-dependent market-data key, never a canonical primary key.

## 2. Source Hierarchy

- Tier 1 (SEC): 13F filing issuer metadata (FACT layer, from SEC information
  tables); `company_tickers.json` / `company_tickers_exchange.json` (CIK ->
  ticker -> title; current ticker only; SEC itself says association is not
  guaranteed complete).
- Tier 2 (OpenFIGI): official v3 mapping API, `ID_CUSIP` (9-char), fallback
  `ID_CUSIP_8_CHR` (8-char), then `ID_ISIN` when an ISIN is available. Save
  figi/compositeFIGI/shareClassFIGI/ticker/exchCode/securityType/name/response
  count/retrieved_at.
- Tier 3 (official exchange / issuer directories): NOT_EVALUATED in v0.2.1;
  used only for manual conflict review if ever needed.
- Tier 4 (manual override / curated exceptions):
  `config/outcome_symbols.csv` and `config/historical_symbols.csv` with
  provenance, rationale, effective dates, reviewer status. Only for
  AMBIGUOUS/CONFLICT/historical gaps that automation cannot resolve.

## 3. Approval Rules (frozen)

### Rule A — two independent high-trust sources

Two independent high-trust sources (e.g., OpenFIGI US ticker AND SEC ticker
file) agree on issuer, share class, US instrument and symbol
-> `VERIFIED_MULTI_SOURCE`.

### Rule B — SEC direct evidence sufficient and unique

SEC evidence is sufficiently unique: exactly one ticker for the normalized
issuer in SEC company-ticker files AND normalized issuer matches the 13F
issuer -> `VERIFIED_EXACT` (SEC-only, only when OpenFIGI returned no usable
result).

### Rule C — OpenFIGI unique exact CUSIP + SEC issuer corroboration (primary)

`VERIFIED_EXACT` requires ALL of:

1. OpenFIGI queried with official `ID_CUSIP` (or `ID_CUSIP_8_CHR` fallback).
2. Exactly one distinct US-exchange ticker after US venue filter, and exactly
   one distinct `shareClassFIGI`.
3. `marketSector == "Equity"` (securityType Common Stock / ADR / similar
   equity-family; consistent with 13F `title_of_class` when it declares ADR or
   a share class).
4. Issuer identity corroborated: normalized OpenFIGI name matches normalized
   13F issuer (abbreviation-aware deterministic normalization) OR SEC ticker
   file title for the same issuer.
5. Share class has no conflict (CUSIP uniquely identifies the class; if the
   issuer has multiple classes, OpenFIGI ticker must match the class implied
   by the CUSIP - e.g., 02079K305 -> GOOGL, 02079K107 -> GOOG).
6. ADR vs ordinary has no conflict (OpenFIGI securityType consistent with 13F
   title_of_class ADR marker when present).
7. US market / exchange identity is reasonable (US venue codes present).
8. No other high-confidence evidence conflicts.

A second independent ticker provider is NOT a hard requirement for Rule C.

## 4. Resolution Status Enum

- `VERIFIED_EXACT` (Rule C or B)
- `VERIFIED_MULTI_SOURCE` (Rule A)
- `VERIFIED_HISTORICAL` (current symbol VERIFIED + historical validity proven
  via provider continuity or curated historical symbol)
- `AMBIGUOUS` (multiple plausible candidates, none dominant)
- `CONFLICT` (high-confidence sources disagree)
- `UNRESOLVED` (no sufficient evidence)
- `NON_EQUITY_OR_UNSUPPORTED` (non-equity / unsupported instrument)
- `DELISTED_OR_TERMINATED` (instrument terminated; no price series)
- `HISTORICAL_IDENTITY_UNRESOLVED` (current symbol verified but history does
  not reach the observation date and no verified historical symbol exists)

Only `VERIFIED_EXACT`, `VERIFIED_MULTI_SOURCE`, `VERIFIED_HISTORICAL` enter
formal outcome research.

## 5. Historical Symbol Rules

Historical observations (info date = filing date of the effective filing) are
covered by exactly one of:

### HISTORICAL_SYMBOL_VERIFIED

Known symbol with `valid_from` / `valid_to` from a source-tagged curated entry
(`config/historical_symbols.csv`) or an authoritative issuer/regulatory
source.

### PROVIDER_CONTINUITY_VERIFIED

The current symbol is used for the full history, and ALL hold:

1. Independent identity source proves rename continuity (same shareClassFIGI
   / issuer before and after).
2. Provider pilot proves the current symbol returns a continuous series
   across the rename (Yahoo chart first bar <= earliest observation info date
   for that security, with adjusted close).
3. No corporate action breaks security identity (splits handled by adjusted
   close; no security-level identity change).

### Otherwise

`HISTORICAL_IDENTITY_UNRESOLVED` — the observation is excluded from outcome
research and counted in coverage as unresolved.

Old tickers are never used blindly (evidence: FB reused by another issuer,
SQ dead).

## 6. ADR / Share-Class Rules

- CUSIP is the share-class authority; the resolver never merges GOOG/GOOGL or
  similar by issuer similarity.
- OpenFIGI `securityType == ADR` must be consistent with the 13F
  `title_of_class` ADR marker; otherwise -> CONFLICT.
- If the 13F title_of_class contains a share-class marker (e.g., "CL A"), the
  resolved instrument must match that class; otherwise -> AMBIGUOUS/CONFLICT.

## 7. Conflict / Missing-Data Rules

- Multiple distinct US tickers for one CUSIP -> AMBIGUOUS (no first-result).
- OpenFIGI and SEC ticker disagree with no resolution -> CONFLICT.
- OpenFIGI 0 results and SEC not unique -> UNRESOLVED.
- No silent fallback: a missing field is never filled by guessing; the record
  carries `UNKNOWN` / `INSUFFICIENT_DATA` and the observation is excluded.

## 8. Priority Universe (R0 / R1 / R2)

Derived from Outcome eligibility only (never from returns or fame):

- R0 = unique CUSIPs present in the O0 eligible observation set
  (A0 signal universe, common window 2023-09-30..2026-06-30).
- R1 = unique CUSIPs present in the O1_2Q eligible observation set
  (A1_2Q persistence universe).
- R2 = unique CUSIPs present in the O1_3Q eligible observation set
  (A1_3Q persistence universe).

Scale-up order maximizes unbiased observation coverage: process R0 first, then
R1, then R2, within each ordered by observation count (descending), with the
hash-based blind sample guaranteed to be covered.

## 9. Pilot Sampling Rule (frozen before running)

### Part A — fixed failure/regression cases

02079K305 (GOOGL share class), 874039100 (TSM ADR), 852234103 (Block rename),
722304102 (PDD unresolved), plus G3643J108 (FLUT, non-US CUSIP honesty case).
Part A is for regression only; it does NOT estimate accuracy.

### Part B — deterministic blind sample

- Universe: R0 union R1 union R2 (unique CUSIPs).
- Selection: SHA256(`cusip:13f-resolution-v0.2.1-pilot-blind`) sorted,
  take first 50 CUSIPs.
- The sample is drawn WITHOUT knowledge of ticker familiarity, manager fame,
  outcomes, or O1/O2 membership beyond eligibility itself.
- Coverage of categories (common equity / share classes / ADR / rename /
  high-frequency / low-frequency / current / stale) is reported after the run.

## 10. Pilot KPIs and False-Match Gate (Gate R3)

Priority: False Verified Rate > Ambiguity Honesty > Historical Identity >
Coverage.

- Golden audit: every `VERIFIED*` pilot record is checked against raw
  evidence (OpenFIGI response, SEC corroboration, Yahoo continuity).
- Gate R3 PASS requires `known_false_verified == 0`. Any false VERIFIED stops
  scale-up until the resolver is fixed. Never mask with more unresolved.
- Target is not 100% coverage; the target is a reliable protocol.

## 11. Scale-Up Rule

Only after Pilot Gate PASS (R3 = 0 false VERIFIED, plus R4 historical identity
honesty). Scale-up never lowers verification rules to raise coverage. Mapping
priority never uses future returns, benchmark-relative returns, O0/O1/O2
results, or popularity.

## 12. Coverage Gates (frozen thresholds)

Denominator = ORIGINAL eligible observations (per variant x split), computed
with the same code path as the frozen Outcome manifest. Mapping must never
redefine the denominator.

- Overall observation coverage per variant: O0 >= 90%, O1_2Q >= 90%,
  O1_3Q >= 90%.
- Per split (development, time holdout, manager holdout, security holdout,
  combined hard holdout): observation coverage >= 85%.
- Differential coverage: |development - each holdout| <= 5 percentage points.
- Directional mapping bias: |positive-activity coverage - negative-activity
  coverage| <= 5 percentage points.
- Variant differential bias: O1/O2 coverage vs O0 coverage must be reported;
  if O1/O2 is systematically higher, mark `VARIANT_MAPPING_BIAS` and do NOT
  run a fair outcome comparison.
- Security-level coverage is reported but is NOT an unlock gate.

## 13. Bias Audit

`reports/research/security_resolution_bias_audit.md` compares: mapped vs
unmapped, high- vs low-frequency securities, common vs ADR, known vs unknown
ticker, dev vs holdout, O0 vs O1 vs O2, positive vs negative activity. Any
material gap degrades the unlock.

## 14. Manual Review Policy

Only AMBIGUOUS / CONFLICT / high-value historical-identity-unresolved enter
the manual queue (`reports/research/manual_resolution_queue.csv`), sorted by
research impact (impacted observation count), never by future outcome.
Plain unresolved low-impact cases are reported as counts, not dumped on the
user.

## 15. Outcome Unlock Rule (Gate R7)

`OUTCOME_UNLOCK=YES` only when ALL are PASS:

- R1 protocol integrity (this document frozen before scale-up)
- R2 provider truth (per-function matrix, OpenFIGI CUSIP verified)
- R3 false mapping (0 known false VERIFIED in golden audit)
- R4 historical identity (no known historical mis-assignment / no future
  leakage; rename/ADR/share-class cases handled)
- R5 coverage (frozen thresholds above, mechanical)
- R6 mapping bias (dev/holdout, positive/negative, variant gaps within frozen
  bounds)
- R7 outcome unlock (R1-R6 AND approved price capability PASS)

If any hard gate FAILS: `OUTCOME_UNLOCK=NO`, precise blockers, minimal manual
queue. No blanket "user must fill CSV".

## 16. Data / Cache Policy

- Raw provider responses cached under `data/resolution_cache/` (gitignored),
  keyed by query + checksum + retrieval date; cache never pollutes the FACT
  layer.
- Resolver artifacts are machine-readable (CSV/JSON/SQLite) under
  `reports/research/` and never write back to holdings/securities.
- Same raw data + same methodology version => same analysis result
  (deterministic runs, fixed seeds, no wall-clock dependence).

## 17. Coupling

```text
FACT
 |
 v
Security Resolution Enrichment
 |
 v
Outcome Research
 |
 v
External Product Review
```

FACT does not import the resolver; the resolver does not read future returns;
outcome does not modify holdings; product does not decide research mapping.

## 18. Freeze Marker

`SECURITY_RESOLUTION_PROTOCOL_FREEZE_VERSION=v0.2.1`

