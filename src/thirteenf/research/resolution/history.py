"""Curated historical-symbol registry (Tier 4 manual override layer)."""

from __future__ import annotations

import csv
from pathlib import Path

from thirteenf.research.resolution.models import HistoricalSymbol


def load_historical_symbols(path: Path | str) -> dict[str, list[HistoricalSymbol]]:
    out: dict[str, list[HistoricalSymbol]] = {}
    p = Path(path)
    if not p.exists():
        return out
    with open(p, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            line for line in fh if not line.lstrip().startswith("#")
        )
        for row in reader:
            cusip = (row.get("cusip") or "").strip().upper()
            symbol = (row.get("symbol") or "").strip().upper()
            if not cusip or not symbol:
                continue
            out.setdefault(cusip, []).append(
                HistoricalSymbol(
                    cusip=cusip,
                    symbol=symbol,
                    valid_from=(row.get("valid_from") or "").strip(),
                    valid_to=(row.get("valid_to") or "").strip(),
                    source=(row.get("source") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return out

