# Variance & Sensitivity

> Generated: 2026-08-24 | Protocol v0.1

## Dominance / Concentration Audit (leave-one-manager-out, H0)

| Variant | Flip fraction | Comparisons | Top flip manager | Top flips |
|---|---|---|---|---|
| A0 | 0.000016 | 128367 | 11 | 2 |
| A1_2Q | 0.012250 | 94611 | 25 | 565 |
| A1_3Q | 0.006351 | 52273 | 25 | 162 |
| A2 | 0.000008 | 128369 | 11 | 1 |

## Variance Gate

- A0: flip fraction ~0.000016 → NOT MANAGER_DOMINATED.
- A1_2Q: flip fraction 0.012 → low, NOT MANAGER_DOMINATED.
- A1_3Q: flip fraction 0.006 → low.
- A2: flip fraction ~0.000008 → NOT MANAGER_DOMINATED.
- No variant shows manager dominance. Time vs dev conclusions agree in direction for A0/A1/A2 → no UNSTABLE flag from this check.

## Pre-registered sensitivity

- A1: 2Q vs 3Q — 3Q is more stable but coverage drops another −69% relative to 2Q; reported, no post-hoc choice.
- A2: UP_DOWN not counted as negative (pre-registered); divergence rate reported separately.
- A3: 3-quantile buckets; HIGH-concentration bucket small (1,468) — marked INSUFFICIENT_SAMPLE for robust inference.

All parameter combinations tested are shown; no grid-search winner selection was performed.