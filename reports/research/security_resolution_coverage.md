# Security Resolution Coverage & Bias Audit (v0.2.1)

> Generated: 2026-08-24T15:08:06.918256+00:00
> Eligible universe securities: 12794

## Observation coverage by variant x split

| Variant | Split | Eligible | Resolved | Coverage % |
|---|---|---|---|---|
| O0 | ALL | 233092 | 163095 | 69.97 |
| O0 | H0_dev | 75385 | 46714 | 61.967 |
| O0 | H1_time_holdout | 38542 | 25932 | 67.282 |
| O0 | H2_manager_holdout | 26451 | 20929 | 79.124 |
| O0 | H3_security_holdout | 19111 | 11927 | 62.409 |
| O0 | H4_combined | 11912 | 9456 | 79.382 |
| O1_2Q | ALL | 64262 | 47450 | 73.838 |
| O1_2Q | H0_dev | 23536 | 15579 | 66.192 |
| O1_2Q | H1_time_holdout | 9880 | 7306 | 73.947 |
| O1_2Q | H2_manager_holdout | 5541 | 4644 | 83.812 |
| O1_2Q | H3_security_holdout | 5931 | 3936 | 66.363 |
| O1_2Q | H4_combined | 3218 | 2679 | 83.25 |
| O1_3Q | ALL | 19634 | 15186 | 77.345 |
| O1_3Q | H0_dev | 7381 | 5116 | 69.313 |
| O1_3Q | H1_time_holdout | 2410 | 1940 | 80.498 |
| O1_3Q | H2_manager_holdout | 1773 | 1549 | 87.366 |
| O1_3Q | H3_security_holdout | 1837 | 1268 | 69.026 |
| O1_3Q | H4_combined | 1091 | 922 | 84.51 |

## Gate evaluation (frozen thresholds)

- O0: overall=69.97% overall_gate=False per_split=False differential=False directional=True **PASS=False**
- O1_2Q: overall=73.838% overall_gate=False per_split=False differential=False directional=True **PASS=False**
- O1_3Q: overall=77.345% overall_gate=False per_split=False differential=False directional=True **PASS=False**
- variant differential: O0=69.97% O1=73.838% O2=77.345% VARIANT_MAPPING_BIAS=True
- security-level coverage: 47.116% (6028/12794)
