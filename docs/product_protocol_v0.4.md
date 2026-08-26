# Product Protocol v0.4 (PRE-REGISTERED)

> Frozen before major UI rework and product acceptance. Changes require a new
> protocol version.

## 1. Final Project Objective (frozen)

> The system exists to improve investment decision quality by providing
> accurate, independent, traceable institutional evidence and structured
> contradiction checks. It must not manufacture predictive confidence that
> the evidence does not support.

This objective outranks dashboard completeness, feature count, visual
richness, manager rankings, stock rankings, user confirmation, and portfolio
convenience.

## 2. Research Governance (frozen)

`PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED` stays. Forbidden to restart:
4Q/5Q persistence, manager weighting, manager skill score, sector tuning,
valuation interaction, ML, LLM signal, predictive consensus, 0-100 score.
v0.4 must not repackage rejected predictive research.

## 3. Scope

v0.4 is a MINIMUM Evidence Product, not full productization. It serves three
tasks only:

- Scenario A - Manager: what changed in this manager's latest filing?
- Scenario B - Security: who changed positions in this security?
- Scenario C - My Portfolio: what facts am I missing (cross-check)?

## 4. Minimum Pages (frozen navigation)

1. Overview - system/filing status first, then What Changed counts
2. Managers - Scenario A
3. Securities - Scenario B
4. Activity Explorer - neutral descriptive sorting
5. My Portfolio - Scenario C (symmetry rule)
6. Methodology - limitations and research history

No predictive page (consensus/scores/trends) in product navigation.

## 5. Language (frozen)

See docs/product_language_policy.md. Forbidden in product path: buy/sell,
bullish/bearish, conviction, high confidence, opportunity, signal, score,
smart money, supportive/contrary thesis, prediction, ranking-as-recommendation.

Activity states allowed (always with underlying counts):
`MORE_ADDS_THAN_REDUCTIONS | MORE_REDUCTIONS_THAN_ADDS | MIXED_ACTIVITY |
NO_RECENT_CHANGE | LOW_BREADTH | STALE_DATA | INSUFFICIENT_DATA`.

No evidence/confidence/consensus score is manufactured.

## 6. FACT / DERIVED FACT / PRESENTATION

Product shows FACT (filing/holdings/shares/value/weight/action/dates/
amendment/CUSIP/resolution) and DERIVED FACT (counts/breadth/persistence/
latest-event/filing-age), plus PRESENTATION (tables/filters/timelines). It
never invents a fourth layer "investment meaning".

## 7. Persistence and Weight Positioning

- Persistence = repeated reported activity only (e.g., "3 managers reported
  additions in at least 2 consecutive reporting periods"). No gap crossing
  across missing filings. Never labeled signal/conviction/confirmation.
- Portfolio weight: report share change and weight change together; never
  translate "shares up / weight down" into "lost conviction" - only state the
  facts.

## 8. Manager Characteristics (frozen)

Factual metadata only: strategy category, position count, concentration,
turnover proxy, filing continuity, active/passive/context category. No
intelligence/quality/skill rank in product.

## 9. My Portfolio Symmetry Rule (frozen)

For every holding, additions/reductions/exits/repeated-adds/repeated-reduces
receive equal visual weight; absent sides show 0. The system does not infer
the user's thesis and never outputs "evidence supports your thesis".

## 10. Contradiction Check (minimum)

Factual contradiction exposure: a security page always shows adds,
reductions, exits, stale information, missing data, amendments. No automatic
"thesis contradicted" verdict.

## 11. Independent Manager Count

Report `holder_entity_count` and `verified_independent_manager_count`
separately; never merge into one. If independence cannot be confirmed:
`UNKNOWN`. No hidden manager weighting; count = count.

## 12. Data Sources

Product reads only local, landed facts: SQLite FACT DB and the committed
resolution/semantic artifacts. No live SEC/OpenFIGI/Yahoo calls from the UI.
Data updates are a separate ingestion workflow.

## 13. Product Task Holdout (frozen)

Deterministic task pool (seed `13f-product-v0.4-task`):

- Security tasks: high breadth, low breadth, mixed activity, persistent
  activity, stale, ADR, share class, unresolved/ambiguous, unfamiliar names.
- Manager tasks: current, stale, concentrated, diversified, amended,
  historically incomplete.
- Portfolio tasks: empty-portfolio adapter behavior only (no synthetic
  portfolio).

Split 70/30 development/holdout by SHA256 hash; never changed for
convenience. The holdout is a product-robustness holdout, NOT a predictive
holdout; evaluation = facts correct, required data visible, quality warnings
visible, query usable, no misleading interpretation.

## 14. Acceptance Gates (frozen)

P1 Fact integrity (0 known mismatch), P2 Derived-evidence integrity, P3
Predictive isolation (product has no outcome/null/falsification dependency and
no predictive language), P4 Symmetry/confirmation-bias control, P5 Data-quality
transparency, P6 Cross-task robustness (holdout reported separately), P7
Retrieval utility (A/B/C answerable), P8 My Portfolio (empty ->
PARTIAL_EMPTY_PORTFOLIO; never fake), P9 No forced insight (neutral results
allowed), P10 Regression (all prior suites PASS; stop rule stays).

## 15. Information Value (two layers)

Layer A (this round): objective information-retrieval utility on holdout
tasks - answer completeness, fact accuracy, provenance. Automatable.
Layer B (protocol only): real-user utility protocol
(docs/real_world_evidence_utility_protocol.md); NO fabricated user results.
`NO_INCREMENTAL_INFORMATION` is a legal, good outcome.

## 16. Scope Freeze

Forbidden: price charts, valuation, financial statements, news, Form 4,
13D/G, IBKR, optimization, alerts, notifications, AI summary, RAG, mobile,
cloud, auth. No new additions.

## 17. Final Status (frozen)

```text
PREDICTIVE_RESEARCH_STOP_RULE       = TRIGGERED
PREDICTIVE_PRODUCT_SIGNAL_STATUS    = DISABLED
PRODUCT_ANTI_OVERFITTING_HARNESS_STATUS = DELIVERED
EVIDENCE_PRODUCT_STATUS             = CANDIDATE_READY_FOR_REAL_USE
PRODUCT_METHODOLOGY_STATUS          = EVIDENCE_ONLY
REAL_WORLD_EVIDENCE_UTILITY         = PENDING_OBSERVATION
REAL_WORLD_DECISION_UTILITY         = PENDING
```

## 18. Freeze Marker

`V0_4_PRODUCT_PROTOCOL_FREEZE_VERSION=v0.4`

