# Holdout Results

> Generated: 2026-08-24 | Protocol v0.1

## Stability by split (higher = more sign-stable)

| Variant | Dev | Time | Manager | Security | Combined |
|---|---|---|---|---|---|
| A0 | 0.3150 | 0.3081 | 0.3483 | 0.3150 | 0.4002 |
| A1_2Q | 0.5766 | 0.6375 | 0.7221 | 0.5752 | 0.6697 |
| A1_3Q | 0.7892 | 0.8851 | 0.8391 | 0.7758 | 0.8701 |
| A2 | 0.2907 | 0.2758 | 0.2680 | 0.2944 | 0.3638 |

## Eligible observations by split

| Variant | Dev | Time | Manager | Security | Combined |
|---|---|---|---|---|---|
| A0 | 75385 | 38542 | 26451 | 19111 | 11912 |
| A1_2Q | 23536 | 9880 | 5541 | 5931 | 3218 |
| A1_3Q | 7381 | 2410 | 1773 | 1837 | 1091 |
| A2 | 75385 | 38542 | 26451 | 19111 | 11912 |

## Interpretation

- A0 stability is consistent across splits (0.29–0.40), i.e. raw action counts are noisy but not split-dependent.
- A1 (persistence) sharply increases stability in every split (0.58–0.89) at the cost of coverage (−69% to −90%).
- A2 (weight-direction) does not improve stability over A0 in any split.
- A3 buckets vary by bucket; HIGH-concentration bucket shows higher stability but very small sample — not robust.
- Recommendation basis: the weakest holdout (time) still supports A1 stability gains; A2 does not clear the incremental bar.