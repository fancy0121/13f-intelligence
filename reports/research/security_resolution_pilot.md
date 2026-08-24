# Security Resolution Pilot (v0.2.1)

> Generated: 2026-08-24
> Protocol: research/security_resolution_protocol_v0.2.1.md (frozen, SHA 4a53ab1)

## 1. Sample

- Part A (fixed regression cases): 02079K305 (GOOGL share class),
  874039100 (TSM ADR), 852234103 (Block SQ->XYZ), 722304102 (PDD),
  G3643J108 (FLUT non-US CUSIP honesty case).
- Part B (deterministic blind sample): 50 CUSIPs selected from the R0/R1/R2
  eligible universe by SHA256(`cusip:13f-resolution-v0.2.1-pilot-blind`),
  no outcome / fame / familiarity input.

## 2. Result

| Status | Count |
|---|---|
| VERIFIED_EXACT | 13 |
| VERIFIED_MULTI_SOURCE | 12 |
| NON_EQUITY_OR_UNSUPPORTED | 4 |
| UNRESOLVED | 26 |
| **Total VERIFIED** | **25 / 55** |

## 3. Regression cases (Part A) - all previous failures FIXED

| CUSIP | Previous (v0.2) | Now | Evidence |
|---|---|---|---|
| 02079K305 | 1GOOGL.MI (foreign) | GOOGL | OpenFIGI ID_CUSIP + US filter; SEC Alphabet Inc. |
| 874039100 | 0LCV.IL (foreign) | TSM | OpenFIGI ADR; SEC TSM/TSMWF set contains TSM |
| 852234103 | XYZ w/o history | XYZ | OpenFIGI current ticker; provider continuity (Yahoo XYZ full history) |
| 722304102 | UNRESOLVED | PDD | OpenFIGI ADR + SEC unique PDD (MULTI_SOURCE) |
| G3643J108 | not probed | FLUT | Rule B: SEC unique ticker FLUT (OpenFIGI has no CUSIP record) |

## 4. Honest non-resolutions (correctly NOT guessed)

- ETF/trust funds with generic issuer names (iShares, SPDR, SSGA, NuShares,
  Fidelity, Victory, Innovator, Themes, Direxion, John Hancock, Tidal,
  Advisors Series, First Trust, Sprott, WisdomTree where SEC title lookup
  missed): UNRESOLVED - never guessed.
- Inari Medical (delisted after Stryker acquisition), Co-Diagnostics,
  Grayscale Bitcoin Mini Trust (CUSIP mismatch/foreign-only): UNRESOLVED
  (no US venue).
- Convertible notes / corporate bonds (Spectrum Brands NOTE, Green Plains
  NOTE, DexCom NOTE, Enphase NOTE): NON_EQUITY_OR_UNSUPPORTED (marketSector
  Corp).

## 5. Resolver correctness corrections made during the pilot iteration

These are correctness fixes (false CONFLICT / false NON_EQUITY), not
verification-rule relaxations; Rules A/B/C and thresholds are unchanged.

1. `SPONSORED ADS` / `ADS` recognized as ADR marker (TSM/PDD were false
   CONFLICT).
2. SEC issuer ticker-set corroboration (OpenFIGI symbol in SEC ticker set,
   e.g., TSM in {TSM, TSMWF}).
3. SEC title (fund full name) corroboration for ETFs whose 13F issuer is the
   trust.
4. "no US venue record" reclassified from NON_EQUITY to UNRESOLVED (a
   delisted equity is not evidence of non-equity).

## 6. Pilot KPI (per protocol priority)

1. False Verified Rate: **0 known false VERIFIED** (golden audit).
2. Ambiguity honesty: multi-US-ticker and non-unique cases stayed UNRESOLVED /
   AMBIGUOUS; no first-result picking.
3. Historical identity: Block handled via provider continuity (XYZ returns
   full 2022+ series); old tickers (SQ, FB) not used.
4. Coverage: correctness prioritized; unresolved ETFs are the main coverage
   cost, quantified in the scale-up coverage report.

