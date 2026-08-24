"""Deterministic permutation null for outcome evaluation.

The null preserves the observation structure (security x quarter groups) and
shuffles signal labels within groups using a fixed seed. Repetitions are
pre-registered; only the frozen comparison rule is used.
"""

from __future__ import annotations

import random

NULL_SEED = "13f-outcome-v0.2-null"


def seeded_rng() -> random.Random:
    return random.Random(NULL_SEED)


def permute_signals(
    values: list[float],
    groups: list[str],
    rng: random.Random,
) -> list[float]:
    """Shuffle values within each group (security x quarter) to preserve
    structure while destroying signal-outcome association."""
    out = values[:]
    by_group: dict[str, list[int]] = {}
    for i, g in enumerate(groups):
        by_group.setdefault(g, []).append(i)
    for idxs in by_group.values():
        vals = [out[i] for i in idxs]
        rng.shuffle(vals)
        for i, v in zip(idxs, vals):
            out[i] = v
    return out

