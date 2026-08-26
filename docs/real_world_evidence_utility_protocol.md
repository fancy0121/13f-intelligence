# Real-World Evidence Utility Protocol

> Frozen 2026-08-26 (v0.4). Used for FUTURE real user sessions; NOT executed
> with fabricated users this round.

## Purpose

Measure whether the evidence product helps real investment-research tasks:
fact retrieval, contradiction exposure, stale/quality detection. NOT whether
prices moved afterwards.

## Recorded per task

- task type (manager/security/portfolio)
- security or manager key
- pre_existing_knowledge
- new_fact_found (bool)
- contradicting_fact_found (bool)
- stale_assumption_corrected (bool)
- quality_risk_found (bool)
- no_incremental_information (bool; legal outcome)
- research_time_saved (qualitative)
- did_it_change_next_research_step (bool)

NOT recorded as primary utility: subsequent price movement.

## Misuse risk

Monitor whether users over-rely on 13F (using institutional adds as a
substitute for fundamentals, treating holder count as a recommendation,
ignoring data age). Such behavior is `MISUSE_RISK`; product design should
reduce it (symmetry, quality transparency, methodology page).

