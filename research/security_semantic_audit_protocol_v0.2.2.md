# Security Semantic Audit Protocol v0.2.2 (PRE-REGISTERED)

> Frozen BEFORE full semantic analysis. Must not be changed to make
> classification results look better. Changes require a new protocol version.
> Status: `POST_RESOLUTION_DIAGNOSTIC / PRE_OUTCOME` (see §7).

## 0. Objective

Answer one question, WITHOUT any forward outcome:

> In the Broad 13F universe, do different economic security types represent
> different institutional behavior semantics, and is there sufficient
> outcome-free factual basis to justify a NEW, narrower
> operating-equity-specific hypothesis (potential v0.3)?

This is a **Hypothesis Eligibility Audit**, NOT an outcome experiment.

## 1. Prior State (preserved, not modifiable)

- v0.2.1 `BROAD_13F_OUTCOME_UNLOCK=NO` (coverage O0 69.97% / O1_2Q 73.84% /
  O1_3Q 77.35%; split coverage, differential, and variant mapping bias FAIL).
- v0.2.1 conclusions remain valid. No old protocol is rewritten. No old
  denominator is redefined.
- This round is outcome-blind: no 3M/6M/12M returns, no benchmark analysis,
  no null model, no hit rates, no future performance labels.

## 2. Revision Disclosure (residual adaptation risk)

We know, before this audit:

- the resolution coverage numbers;
- that fund/ETF pooled vehicles are a major source of unresolved observations;
- the v0.2.1 gate failures.

We have NOT seen any forward outcome. This round is therefore
`POST_RESOLUTION_DIAGNOSTIC / PRE_OUTCOME`. The hypothesis-generation is NOT
fully ex-ante; residual adaptation risk exists because the audit question was
chosen after observing resolution failures. This is recorded and accepted;
any v0.3 preregistration must be a fresh, independent protocol.

## 3. Security Economic-Type Taxonomy (frozen)

Every eligible security is assigned exactly one of:

- `OPERATING_COMMON_EQUITY` - operating-company common stock
- `OPERATING_ADR` - US ADR/ADS exposure of a foreign operating company
- `OPERATING_OTHER_EQUITY` - other clearly operating-company equity (units,
  tracking stock, NY registry shares, MLP, limited partnership interests)
- `ETF` - exchange-traded pooled vehicle
- `MUTUAL_OR_POOLED_FUND` - mutual fund / other pooled investment vehicle
- `CLOSED_END_FUND` - closed-end fund
- `REIT_OR_SPECIAL_EQUITY` - REIT / royalty trust / other special equity
- `PREFERRED_OR_HYBRID` - preferred stock or hybrid instruments
- `OTHER_13F_SECURITY` - other 13F-reportable security (rights, warrants)
- `NON_EQUITY_OR_UNSUPPORTED` - notes/bonds or unsupported instruments
- `UNKNOWN` - insufficient evidence (never force-classified)

Pooled comparison group (frozen, used only descriptively):
`POOLED_VEHICLE = ETF | MUTUAL_OR_POOLED_FUND | CLOSED_END_FUND`.
Operating audit set (frozen):
`OPERATING_EQUITY_AUDIT_SET = OPERATING_COMMON_EQUITY | OPERATING_ADR |
OPERATING_OTHER_EQUITY`.

## 4. Source Hierarchy (frozen)

1. SEC filing metadata (13F information table issuer + title_of_class).
2. OpenFIGI (cached v0.2.1 responses): marketSector, securityType, name,
   FIGI identities.
3. Issuer / fund official evidence (SEC company-ticker titles).
4. Official exchange evidence (US venue codes).

Forbidden classification bases: Yahoo Search, LLM inference, issuer-name
fuzzy match alone, future returns, user portfolio, manager fame.

## 5. Classification Rules (frozen)

Deterministic, rule-based, provenance-tagged. `classification_status`:
`VERIFIED` (OpenFIGI primary), `PROVISIONAL` (title/issuer heuristics only),
`CONFLICT` (sources disagree), `UNKNOWN` (no evidence).

Primary rules (OpenFIGI, status=VERIFIED):

- T1 marketSector == "Corp" OR title_of_class contains "NOTE" -> NON_EQUITY_OR_UNSUPPORTED
- T2 securityType == "ETP" OR title_of_class contains "ETF" -> ETF
- T3 securityType == "Closed-End Fund" -> CLOSED_END_FUND
- T4 securityType in {"Mutual Fund", "Fund"} OR pooled issuer + non-common
  title -> MUTUAL_OR_POOLED_FUND
- T5 securityType == "ADR" OR title_of_class contains "ADR"/"ADS" ->
  OPERATING_ADR
- T6 securityType == "REIT" OR securityType == "Royalty Trst" ->
  REIT_OR_SPECIAL_EQUITY
- T7 securityType == "Preferred Stock" -> PREFERRED_OR_HYBRID
- T8 securityType == "Common Stock" AND not pooled issuer ->
  OPERATING_COMMON_EQUITY
- T9 securityType in {"Unit","Tracking Stk","NY Reg Shrs","Ltd Part","MLP"}
  AND not pooled issuer -> OPERATING_OTHER_EQUITY
- T10 securityType in {"Right","Warrant"} -> OTHER_13F_SECURITY

Fallback rules (no usable OpenFIGI, status=PROVISIONAL):

- F1 title contains "NOTE"/"%" -> NON_EQUITY_OR_UNSUPPORTED
- F2 title contains "ETF" -> ETF
- F3 title contains "ADR"/"ADS" -> OPERATING_ADR
- F4 pooled issuer tokens (exact token in
  {TR,TRUST,FUND,FD,FDS,ETF,SERIES,SER,PORTFOLIO}) -> MUTUAL_OR_POOLED_FUND
- F5 title in {"COM","SHS","ORD","CL A","CL B","CL C","CAP STK CL A",
  "COMMON STOCK","COM NEW"} -> OPERATING_COMMON_EQUITY
- F6 title in {"UNIT","PFD"} -> OPERATING_OTHER_EQUITY / PREFERRED_OR_HYBRID
  (by keyword)
- F7 otherwise -> UNKNOWN (status=UNKNOWN, never guessed)

Conflict rule (C1): if OpenFIGI type and explicit title marker disagree
(e.g., OpenFIGI Common Stock + title "ETF"), classification follows the
explicit title marker with status=CONFLICT and both sources recorded.

## 6. Classification Provenance

Per security: `security_id, cusip, economic_type, classification_status,
classification_sources, classification_reason, classification_version,
classified_at`. Only `VERIFIED` classifications enter strong semantic
analysis; `PROVISIONAL`/`UNKNOWN`/`CONFLICT` are reported separately.

## 7. Independence From Resolution

Semantic classification NEVER depends on resolver status or ticker
resolution. An unresolved-ticker fund is still classified ETF if evidence
says so; a VERIFIED ticker is never automatically operating equity. The
classification module MUST NOT import or call outcome modules.

## 8. Sample Definitions (frozen)

- Eligible universe: the v0.2.1 R0/R1/R2 universe (12,794 CUSIPs), i.e., all
  securities with >=1 position change in the common window
  2023-09-30..2026-06-30.
- Variants: O0 (all), O1_2Q (2Q persistence), O1_3Q (3Q persistence) with the
  frozen per-part denominators from the v0.2.1 manifest.
- Splits: H0_dev, H1_time_holdout, H2_manager_holdout, H3_security_holdout,
  H4_combined (frozen manifests).

## 9. Comparison Metrics (frozen)

Behavior descriptors (pre-outcome only) for operating vs pooled:

- NEW / ADD / REDUCE / EXIT / UNCHANGED rates
- average and median holding persistence (consecutive same-direction quarters)
- position-count distribution (positions per filing per manager)
- reported portfolio-weight distribution (weight_now)
- turnover proxy ((NEW+EXIT)/(ADD+REDUCE+NEW+EXIT))
- manager participation distribution (distinct managers per security)
- quarter-to-quarter action reversal rate
- concentration proxy (top-10 share within manager filing) when available

Effect size priority: absolute difference, relative difference, distribution
shift, standardized effect size (Cohen's d) where simple; sample size always
reported. Statistical tests: few, pre-registered, transparent (chi-square on
the action table is the only planned test; descriptive only).

## 10. Bias Diagnostics (frozen)

- Manager composition confounding: within-manager operating-vs-pooled summary;
  flag `MANAGER_COMPOSITION_CONFOUNDED` if a few managers drive the gap.
- Time composition: per-quarter operating-vs-pooled descriptor; flag
  `TIME_COMPOSITION_SENSITIVE` if effect is quarter-specific.
- Position-size confounding: weight distributions per group reported; never
  interpret larger position as stronger conviction.
- Persistence composition: share of O1_2Q/O1_3Q eligibility within operating
  vs pooled; answer whether A1's stability is partly universe-composition
  driven.
- Split composition: report type composition per split; flag
  `SECURITY_TYPE_SPLIT_SHIFT` if any type share shifts > 5pp across splits.
- Selection bias: Operating Equity audit set vs Broad universe on manager,
  quarter, direction, split, position size, observation frequency,
  persistence eligibility.
- Missingness: within Operating Equity audit set, mapped vs unresolved
  observations on manager/quarter/direction/persistence/position size/split;
  output `OPERATING_EQUITY_MISSINGNESS_STATUS` in
  {LOW_CONCERN, MODERATE_CONCERN, HIGH_CONCERN, INSUFFICIENT_DATA}.
- Variant mapping bias decomposition: split v0.2.1 VARIANT_MAPPING_BIAS into
  (a) security-type composition effect and (b) within-type mapping bias.

## 11. Partial Identification Recommendation

Only a method note: whether future v0.3 outcome (if any) with non-zero
unresolved observations should use worst/best-case bounds or another simple
partial-identification sensitivity. Verdict limited to
`RECOMMENDED | NOT_NEEDED | DEFER`. No future returns are used.

## 12. v0.3 Hypothesis Justification Criteria (frozen, Gate S6)

`V0_3_OPERATING_EQUITY_HYPOTHESIS=JUSTIFIED_FOR_NEW_PREREGISTRATION` only if
ALL of:

- J1 Semantic coherence: operating equity and pooled vehicles are clearly
  distinct economic structures.
- J2 Observable behavioral distinction: non-trivial, repeatable pre-outcome
  behavior differences (or pooled exposure clearly represents a different
  manager behavior class).
- J3 Not merely mapping convenience: justification is NOT resolver coverage.
- J4 Selection audit acceptable: no unacceptable manager/time/direction
  distortion in the Operating Equity audit set.
- J5 Research-question coherence: hypothesis relates directly to the project
  goal (institutional stock-selection evidence).

Otherwise `NOT_JUSTIFIED` or `INSUFFICIENT_EVIDENCE` (with what is missing).

## 13. Research Stop Rule (frozen governance)

If (1) broad hypothesis cannot pass, (2) operating-equity v0.3 is approved
and completed, and (3) A0/2Q/3Q persistence still shows no incremental
economic value in frozen outcome tests, then STOP predictive-signal research
(no 4Q/5Q persistence, no manager score, no sector tuning, no ML, no feature
search) and convert the system to an Institutional Evidence System. Written
to `docs/research_stop_rule.md`.

## 14. Gates (frozen)

- S1 Protocol integrity: this file frozen before full analysis.
- S2 Classification integrity: golden/deterministic sample
  `known_false_classification = 0` (or downgrade).
- S3 Accounting integrity: every eligible security/observation lands in a
  class or UNKNOWN/CONFLICT; nothing silently disappears.
- S4 Outcome blindness: no forward outcome used for classify/select/filter/
  justify.
- S5 Bias audit: manager/quarter/direction/split/position-size/persistence
  quantified; cannot show operating-equity is an artificial sample.
- S6 Hypothesis eligibility: mechanical J1-J5 -> verdict.

Even if S6 = JUSTIFIED, this round STOPS; no v0.3 outcome is started.

## 15. Freeze Marker

`SECURITY_SEMANTIC_AUDIT_PROTOCOL_FREEZE_VERSION=v0.2.2`

