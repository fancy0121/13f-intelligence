"""Deterministic research splits (time / manager / security).

All splits use fixed seeds and SHA256 hashing. Splits are computed from
objective identifiers (CIK, CUSIP) only - never from outcomes, fame, or
experimental results.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

MANAGER_SPLIT_SEED = "13f-research-v0.1-manager"
SECURITY_SPLIT_SEED = "13f-research-v0.1-security"

# Protocol v0.1 frozen common window (12 quarters) and dev/holdout boundary.
COMMON_WINDOW_START = "2023-09-30"
COMMON_WINDOW_END = "2026-06-30"
DEV_WINDOW_END = "2025-06-30"  # dev = earliest 8 quarters; holdout = last 4


def _hash_bucket(key: str, seed: str, pct: int) -> bool:
    """Return True if key lands in the 'development' bucket (< pct)."""
    digest = hashlib.sha256(f"{key}:{seed}".encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) % 100
    return value < pct


def time_split(
    periods: list[str],
    *,
    dev_count: int = 8,
) -> tuple[list[str], list[str]]:
    """Chronological split: earliest dev_count periods = development, the rest
    = time holdout. Deterministic given the sorted input."""
    ordered = sorted(set(periods))
    if len(ordered) <= dev_count:
        # Not enough periods for a holdout: development takes all that exist,
        # holdout is empty and reported as INSUFFICIENT_SAMPLE downstream.
        return ordered, []
    return ordered[:dev_count], ordered[dev_count:]


def protocol_time_split(periods: list[str]) -> tuple[list[str], list[str]]:
    """Protocol v0.1 frozen chronological split over the 12-quarter common
    window. Any period outside the window is excluded from research."""
    in_window = sorted(
        p
        for p in set(periods)
        if COMMON_WINDOW_START <= p <= COMMON_WINDOW_END
    )
    dev = [p for p in in_window if p <= DEV_WINDOW_END]
    hold = [p for p in in_window if p > DEV_WINDOW_END]
    return dev, hold


def manager_split(
    conn: sqlite3.Connection,
    *,
    dev_pct: int = 70,
    seed: str = MANAGER_SPLIT_SEED,
) -> dict[int, str]:
    """Map manager_id -> 'development' | 'holdout' (deterministic)."""
    rows = conn.execute("SELECT manager_id, cik FROM managers").fetchall()
    out: dict[int, str] = {}
    for manager_id, cik in rows:
        dev = _hash_bucket(str(cik), seed, dev_pct)
        out[manager_id] = "development" if dev else "holdout"
    return out


def security_split(
    conn: sqlite3.Connection,
    *,
    dev_pct: int = 80,
    seed: str = SECURITY_SPLIT_SEED,
) -> dict[str, str]:
    """Map cusip -> 'development' | 'holdout' (deterministic)."""
    rows = conn.execute(
        "SELECT DISTINCT cusip FROM securities WHERE cusip != ''"
    ).fetchall()
    out: dict[str, str] = {}
    for (cusip,) in rows:
        dev = _hash_bucket(cusip, seed, dev_pct)
        out[cusip] = "development" if dev else "holdout"
    return out


def write_manifest(path: Path, rows: list[dict], header: str = "") -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        if header:
            fh.write(f"# {header}\n")
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["id"])
        writer.writeheader()
        writer.writerows(rows)
