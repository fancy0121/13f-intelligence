# Leakage Audit

> Generated: 2026-08-24 | Protocol v0.1

| Item | Risk | Observed status | Residual risk |
|---|---|---|---|
| Quarter-end vs filing-date leakage | LOW | Observations carry info_date = effective filing_date (amendment-aware); report_period is never used as information time. | Residual: intra-quarter position changes before filing are unknown by design. |
| Amendment timing | LOW | effective_filing_dates prefers 13F-HR/A (newest filing date) per period; tested in tests/research/test_information_time.py. | Residual: same-day filings ordered by filing_id. |
| Future ticker metadata leakage | LOW | Research uses CUSIP/security_id; ticker is display-only and mostly UNRESOLVED. | Residual: none for analysis; mapping bias audited separately. |
| Future manager classification leakage | LOW | No manager classification used in A0/A1/A2; A3 buckets use data-derived characteristics from FACT LAYER only. | Residual: characteristics are full-period (not point-in-time); see note. |
| Portfolio leakage | LOW | config/portfolio.csv is empty and never read by research CLI. | Residual: none in this run. |
| Security selection leakage | LOW | Security split is deterministic SHA256(CUSIP+seed); no outcome-based selection. | Residual: none. |
| Outcome-to-feature leakage | N/A | No outcome/price data used; FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER. | Residual: none (no outcome pipeline). |
| Survivorship bias | KNOWN | 29-manager universe is human-curated (not a random sample of all 13F filers). UNIVERSE LIMITATION documented; conclusions apply only to this curated set. | Residual: cannot generalize to all institutional investors. |
| Stale manager data | LOW | Stale managers (Scion, Greenlight, Vanguard parent) remain in observations and are flagged by quality events; no dropping based on outcomes. | Residual: stale data may understate recent signals for those managers. |
| Confidential-treatment limitations | KNOWN | 13F may omit confidential positions; absent holdings are not interpreted as 'not held'. | Residual: inherent to 13F data. |

## Note: A3 manager characteristics are full-period
A3 buckets use manager characteristics computed over all available filings (not point-in-time). This is a known limitation for causal claims; A3 is descriptive/EXPERIMENTAL and not a production rule.