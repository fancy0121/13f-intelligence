# Gate 2 - Analytical Correctness Report

> Generated: 2026-08-24
> Transitions verified against SEC raw XML: **30**
> Mismatches: **0**
> shares-increase-but-weight-decrease cases found: **2**

## Coverage

| Type | Verified |
|---|---|
| NEW | 10 |
| ADD | 7 |
| REDUCE | 5 |
| EXIT | 5 |
| UNCHANGED | 3 |

## Verdict: **GATE2=PASS**

## Sample detail

- G0176J109 (G0176J109, stock) manager=1 period=2025-06-30 db=NEW expected=NEW -> OK
- 02005N100 (02005N100, stock) manager=1 period=2024-03-31 db=NEW expected=NEW -> OK
- 02005N100 (02005N100, stock) manager=1 period=2025-06-30 db=NEW expected=NEW -> OK
- 02079K305 (02079K305, stock) manager=1 period=2025-09-30 db=NEW expected=NEW -> OK
- 02079K107 (02079K107, stock) manager=1 period=2026-03-31 db=NEW expected=NEW -> OK
- 02079K305 (02079K305, stock) manager=1 period=2025-12-31 db=ADD expected=ADD -> OK
- 02079K305 (02079K305, stock) manager=1 period=2026-03-31 db=ADD expected=ADD -> OK
- 02079K305 (02079K305, stock) manager=1 period=2026-06-30 db=ADD expected=ADD -> OK
- 02079K107 (02079K107, stock) manager=1 period=2026-06-30 db=ADD expected=ADD -> OK
- 14040H105 (14040H105, stock) manager=1 period=2024-12-31 db=ADD expected=ADD -> OK
- 14040H105 (14040H105, stock) manager=1 period=2024-06-30 db=REDUCE expected=REDUCE -> OK
- 14040H105 (14040H105, stock) manager=1 period=2026-06-30 db=REDUCE expected=REDUCE -> OK
- 16119P108 (16119P108, stock) manager=1 period=2024-09-30 db=REDUCE expected=REDUCE -> OK
- 16119P108 (16119P108, stock) manager=1 period=2024-12-31 db=REDUCE expected=REDUCE -> OK
- 21036P108 (21036P108, stock) manager=1 period=2026-03-31 db=REDUCE expected=REDUCE -> OK
- G0176J109 (G0176J109, stock) manager=1 period=2026-03-31 db=EXIT expected=EXIT -> OK
- 02005N100 (02005N100, stock) manager=1 period=2025-03-31 db=EXIT expected=EXIT -> OK
- 023135106 (023135106, stock) manager=1 period=2025-03-31 db=EXIT expected=EXIT -> OK
- 023135106 (023135106, stock) manager=1 period=2026-03-31 db=EXIT expected=EXIT -> OK
- 025816109 (025816109, stock) manager=1 period=2025-03-31 db=EXIT expected=EXIT -> OK
- G0176J109 (G0176J109, stock) manager=1 period=2025-09-30 db=UNCHANGED expected=UNCHANGED -> OK
- G0176J109 (G0176J109, stock) manager=1 period=2025-12-31 db=UNCHANGED expected=UNCHANGED -> OK
- 02005N100 (02005N100, stock) manager=1 period=2024-06-30 db=UNCHANGED expected=UNCHANGED -> OK
- H1467J104 (H1467J104, stock) manager=1 period=2024-03-31 db=ADD expected=ADD -> OK
- 512816109 (512816109, stock) manager=1 period=2025-09-30 db=ADD expected=ADD -> OK
- 023135106 (023135106, stock) manager=1 period=2024-03-31 db=NEW expected=NEW -> OK
- 023135106 (023135106, stock) manager=1 period=2025-06-30 db=NEW expected=NEW -> OK
- 025816109 (025816109, stock) manager=1 period=2024-03-31 db=NEW expected=NEW -> OK
- 025816109 (025816109, stock) manager=1 period=2025-06-30 db=NEW expected=NEW -> OK
- G0403H108 (G0403H108, stock) manager=1 period=2024-03-31 db=NEW expected=NEW -> OK