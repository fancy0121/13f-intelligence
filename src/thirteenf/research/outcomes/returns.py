"""Forward-return calculation from information_available_date.

Horizons are fixed at 3M / 6M / 12M trading days. The start bar is the first
trading day ON or AFTER information_available_date; the end bar is start + N
bars. Uses adjusted close (total-return-compatible) when available.
"""

from __future__ import annotations

from datetime import date, datetime


def first_trading_day_after(dates: list[str], info_date: str) -> int | None:
    """Return index of first bar with date >= info_date, else None."""
    target = date.fromisoformat(info_date)
    for i, d in enumerate(dates):
        if date.fromisoformat(d) >= target:
            return i
    return None


def forward_return(
    dates: list[str],
    adjclose: list[float | None],
    info_date: str,
    horizon: int,
) -> float | None:
    """Return (adjclose[end] / adjclose[start]) - 1 for a fixed trading-day
    horizon, or None when insufficient data."""
    start = first_trading_day_after(dates, info_date)
    if start is None:
        return None
    end = start + horizon
    if end >= len(dates):
        return None
    if adjclose[start] is None or adjclose[end] is None:
        return None
    if adjclose[start] == 0:
        return None
    return (adjclose[end] / adjclose[start]) - 1.0

