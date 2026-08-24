"""Security Master: CUSIP -> ticker resolution with provenance.

CUSIP is the canonical identity. Ticker is derived only from curated,
source-tagged mappings; anything uncertain stays UNRESOLVED (ticker=None).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecurityMapping:
    cusip: str
    ticker: str | None
    issuer: str | None
    share_class: str | None
    mapping_status: str
    mapping_source: str
    verified_at: str
    verified_by: str
    notes: str


def load_mappings(path: Path) -> dict[str, SecurityMapping]:
    """Load curated CUSIP mapping CSV into {cusip: SecurityMapping}."""
    mappings: dict[str, SecurityMapping] = {}
    if not path.exists():
        return mappings
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            cusip = (row.get("cusip") or "").strip().upper()
            if not cusip:
                continue
            status = (row.get("mapping_status") or "UNRESOLVED").strip().upper()
            mappings[cusip] = SecurityMapping(
                cusip=cusip,
                ticker=(row.get("ticker") or "").strip() or None,
                issuer=(row.get("issuer") or "").strip() or None,
                share_class=(row.get("share_class") or "").strip() or None,
                mapping_status=status,
                mapping_source=(row.get("mapping_source") or "").strip(),
                verified_at=(row.get("verified_at") or "").strip(),
                verified_by=(row.get("verified_by") or "").strip(),
                notes=(row.get("notes") or "").strip(),
            )
    return mappings


def resolve(mappings: dict[str, SecurityMapping], cusip: str) -> SecurityMapping:
    """Return mapping for CUSIP; unknown CUSIPs become UNRESOLVED."""
    key = (cusip or "").strip().upper()
    if key in mappings:
        return mappings[key]
    return SecurityMapping(
        cusip=key,
        ticker=None,
        issuer=None,
        share_class=None,
        mapping_status="UNRESOLVED",
        mapping_source="",
        verified_at="",
        verified_by="",
        notes="not in curated mapping",
    )

