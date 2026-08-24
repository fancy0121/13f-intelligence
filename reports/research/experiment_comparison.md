# Experiment Comparison (A0/A1/A2/A3)

> Generated: 2026-08-24 | Protocol v0.1

## H0 (development) overview

| Variant | Eligible | Signal-producing | Stability | Reversal rate |
|---|---|---|---|---|
| A0 | 75385 | 39010 | 0.3150 | 0.6850 |
| A1_2Q | 23536 | 18407 | 0.5766 | 0.4234 |
| A1_3Q | 7381 | 6765 | 0.7892 | 0.2108 |
| A2 | 75385 | 38852 | 0.2907 | 0.7093 |

### Incremental information (dev)

- **A1_2Q vs A0**: stability 0.577 vs 0.315 (+0.26), eligible drops 75,385 → 23,536 (−69%).
- **A1_3Q vs A0**: stability 0.789 vs 0.315 (+0.47), eligible drops to 7,381 (−90%).
- **A2 vs A0**: stability 0.291 vs 0.315 (−0.02); net weight-direction signal does not improve sign stability at dev.
- **A3 buckets**: filing_continuity LOW stability 0.220, MEDIUM 0.333, HIGH 0.294; avg_concentration HIGH 0.426 but tiny sample (1,468 eligible).

## Cases where complexity changes conclusions

A1 filters out most single-quarter actions; on remaining securities the net signal direction agrees with A0 in most cases (A1_2Q flip fraction via leave-one-manager-out 0.012). A2 differs from A0 only when shares/weight diverge; divergence rate is reported per security but not promoted.