# v0.3 Falsification Report

Mechanical application of pre-registered O1/O2 falsification criteria (3M primary).

| item | value |
|---|---|
| O1_FAIL_REASONS | ["NO_MEANINGFUL_IMPROVEMENT_OVER_O0", "NULL_COMPARISON_FAILS", "MISSINGNESS_GATES_FAIL"] |
| O2_FAIL_REASONS | ["NO_MEANINGFUL_IMPROVEMENT_OVER_O0", "NULL_COMPARISON_FAILS", "MISSINGNESS_GATES_FAIL", "NO_INCREMENT_OVER_O1"] |
| O1_PASS | false |
| O2_PASS | false |
| SIMPLEST_SURVIVING_MODEL | "O0" |
| PREDICTIVE_RESEARCH_STOP_RULE | "TRIGGERED" |
| PRODUCT_CANDIDATE_STATUS | "NO_CANDIDATE" |
| notes | {"o0_dev_median_3M": -0.026169, "o1_dev_median_3M": -0.028302, "o2_dev_median_3M": -0.030654, "o1_null_p95_3M": -0.028301629854122545, "o1_exceeds_null_p95": false} |

Right-censored counts:

| variant | horizon | censored |
|---|---|---|
| O0 | 3M | 29583 |
| O0 | 6M | 46989 |
| O0 | 12M | 80345 |
| O1_2Q | 3M | 12016 |
| O1_2Q | 6M | 18372 |
| O1_2Q | 12M | 22501 |
| O1_3Q | 3M | 5703 |
| O1_3Q | 6M | 5703 |
| O1_3Q | 12M | 7419 |
