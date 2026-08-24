# Final Recommendation

> Generated: 2026-08-24 | Protocol v0.1

## Answers

### A0 — True minimum baseline
**KEEP.** Raw equal-weight action counts are the correct reference; they are the only method with full coverage and consistent behavior across all splits.

### A1 — Persistence (2Q/3Q)
**WEAKLY_SUPPORTED (2Q) / EXPERIMENT_AGAIN (3Q).** 2Q persistence improves sign stability in every split (+0.26 dev, +0.33 time) but reduces coverage by 69%. 3Q is even more stable but coverage drops to ~10% — insufficient for broad use; revisit with longer history.

### A2 — Portfolio Weight
**NO_INCREMENTAL_VALUE.** Weight-direction signal is no more stable than A0 in any split (dev 0.291 vs 0.315) and adds divergence complexity without evidence of incremental information.

### A3 — Manager Characteristics
**NO_INCREMENTAL_VALUE / INSUFFICIENT_EVIDENCE.** Bucket stability differences are small and the most interesting bucket (concentration HIGH) has an insufficient sample. Not worth promoting; do not build a precise manager 'smart score'.

### A4 — Strategy Diversity
**NOT_EXECUTED_OPTIONAL.** Not implemented; no evidence either way. Do not build unless a cheap, data-driven group proxy is available.

## What We Should Keep
- A0 fact counts (NEW/ADD/REDUCE/EXIT/UNCHANGED, net directional).
- A1 2Q persistence as an EXPERIMENTAL filter (not production).
- The research harness itself (splits, manifests, leakage audit).

## What We Should NOT Build
- Precise manager signal_quality scores (0.873-style).
- Normalized 0–100 consensus as a headline number.
- A2 weight-direction as a promoted signal (no incremental value).
- Strategy diversity / clustering / ML correlation graphs in v0.1.1.

## Candidate Product Rules
- None are promoted in this phase. A1 2Q persistence is the only `CANDIDATE_FOR_PRODUCT_APPROVAL`-eligible candidate, and only as an EXPERIMENTAL filter pending external review and longer history.

## Gates
- Protocol Integrity: **PASS** (frozen commit 69e728f).
- Leakage: **PASS** (no severe leakage found; residual risks documented).
- Reproducibility: **PASS** (rerun artifacts identical; only manifest timestamp differs).
- Baseline Comparison: **PASS** — A1_2Q weakly supported; A2/A3 NO_INCREMENTAL_VALUE; A0 KEEP.
- Holdout Robustness: **PASS** — directions consistent across splits; no dev-good/holdout-bad inversion.
- Simplicity: **PASS** — A0 remains the simplest surviving model; no complex rule promoted.
- Real-World Decision Utility: **PENDING** (unchanged).