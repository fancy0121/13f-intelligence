# v0.3 Missingness Audit

MISSINGNESS_GOVERNANCE_STATUS=FAIL

## Gates M1-M5

| gate | value | PASS |
|---|---|---|
| M1_overall_80 | 90.41 | True |
| M2_split_75 | {"H0_dev": 85.88, "H1_time_holdout": 94.301, "H2_manager_holdout": 90.044, "H3_security_holdout": 86.04, "H4_combined": 93.877} | True |
| M3_differential_7.5 | {"H1_time_holdout": 8.421, "H2_manager_holdout": 4.164, "H3_security_holdout": 0.16, "H4_combined": 7.997} | False |
| M4_directional_7.5 | 2.15 | True |
| M5_variant_7.5 | {"O1_2Q": 0.632, "O1_3Q": 0.997} | True |

## Per variant

| variant | eligible | overall_coverage | positive | negative |
|---|---|---|---|---|
| O0 | 147940 | 90.41 | 91.254 | 89.104 |
| O1_2Q | 43493 | 91.042 | 91.881 | 89.836 |
| O1_3Q | 14035 | 91.407 | 92.315 | 89.948 |

## Per split (O0)

| split | coverage |
|---|---|
| H0_dev | 85.88 |
| H1_time_holdout | 94.301 |
| H2_manager_holdout | 90.044 |
| H3_security_holdout | 86.04 |
| H4_combined | 93.877 |
