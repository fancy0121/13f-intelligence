# Research Stop Rule (frozen governance)

> Added: 2026-08-24 (v0.2.2). Frozen; not negotiable by any single research
> round.

## 1. Purpose

Prevent open-ended predictive-signal search. If the evidence shows that
frozen institutional-behavior signals do not carry incremental economic
value, the project stops searching for alpha and converts to an
Institutional Evidence System.

## 2. Trigger (all three conditions)

Research stops predictive-signal search when ALL of:

1. **Broad hypothesis cannot pass**: the broad 13F outcome hypothesis remains
   locked by resolution/bias gates or is falsified in a frozen outcome test
   (`BROAD_13F_OUTCOME_UNLOCK=NO` with no approved remediation).
2. **Operating Equity v0.3 is approved and completed**: a new v0.3
   operating-equity hypothesis (if justified) is pre-registered, run with
   frozen tests, and completed.
3. **No incremental economic value**: A0 / 2Q / 3Q persistence still shows no
   incremental economic value in the frozen outcome tests (per the frozen
   falsification criteria), i.e., the simplest model survives.

## 3. What is forbidden once triggered

Without a new independent theory and external approval, the project must NOT
search:

- 4Q / 5Q persistence
- manager scores / manager skill ranking
- sector or valuation interaction tuning
- ML / feature combinations
- any new persistence threshold

## 4. What the system becomes

`INSTITUTIONAL EVIDENCE SYSTEM` - productize factual evidence:

- SEC holdings history
- NEW / ADD / REDUCE / EXIT facts
- portfolio-weight facts
- persistent-activity facts
- manager/stock reverse lookup
- filing freshness and amendment awareness
- evidence provenance and data quality

These capabilities have independent product value and are NOT invalidated by
outcome failure (see protocol v0.2.2 §35).

## 5. Governance

- This rule is recorded in `docs/rejected_or_frozen_ideas.md` and this file.
- Any research that would resume predictive-signal search must first obtain
  external approval and a new theory-based preregistration.

