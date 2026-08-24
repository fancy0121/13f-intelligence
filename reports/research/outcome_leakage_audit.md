# Outcome Leakage Audit (v0.2)

> Generated: 2026-08-24

| Item | Status | Detail |
|---|---|---|
| Quarter-end vs filing-date leakage | N/A (no outcome run) | Protocol mandates info date = filing_date; framework enforces first_trading_day_after(info_date). |
| Amendment timing | N/A | effective_filing_dates prefers 13F-HR/A; outcome start follows amendment publication. |
| Symbol-history leakage | DESIGNED | Curated mappings carry effective_date; unresolved symbols never guessed. |
| Corporate-action leakage | DESIGNED | Adjusted close + events; split fixture tested. |
| Benchmark lookahead | N/A | No benchmark series fetched in evaluation (no provider approved). |
| Future delisting knowledge | N/A | Missing prices → OUTCOME_UNRESOLVED_SECURITY; no survivorship filtering. |
| Outcome-based sample filtering | N/A | No outcome sample created. |
| Holdout reuse | PASS | Manifests reused from v0.1; no rehash. |

Conclusion: no severe leakage identified at framework level; formal evaluation not executed (no approved provider).