"""CUSIP -> market symbol resolution (provenance-aware).

Only curated, source-tagged mappings are accepted. If a CUSIP is not in the
curated map, it is OUTCOME_UNRESOLVED_SECURITY - never guessed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SymbolMapping:
    cusip: str
    symbol: str
    exchange: str
    source: str
    effective_date: str
    verified_at: str
    verified_by: str
    notes: str


def load_symbol_mappings(path: Path) -> dict[str, SymbolMapping]:
    mappings: dict[str, SymbolMapping] = {}
    if not path.exists():
        return mappings
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            cusip = (row.get("cusip") or "").strip().upper()
            symbol = (row.get("symbol") or "").strip().upper()
            if not cusip or not symbol:
                continue
            mappings[cusip] = SymbolMapping(
                cusip=cusip,
                symbol=symbol,
                exchange=(row.get("exchange") or "").strip(),
                source=(row.get("source") or "").strip(),
                effective_date=(row.get("effective_date") or "").strip(),
                verified_at=(row.get("verified_at") or "").strip(),
                verified_by=(row.get("verified_by") or "").strip(),
                notes=(row.get("notes") or "").strip(),
            )
    return mappings


def resolve(mappings: dict[str, SymbolMapping], cusip: str) -> SymbolMapping | None:
    key = (cusip or "").strip().upper()
    return mappings.get(key)

