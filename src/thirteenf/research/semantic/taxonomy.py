"""Economic-type taxonomy and classification rules (frozen in v0.2.2 protocol)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class EconomicType(str, Enum):
    OPERATING_COMMON_EQUITY = "OPERATING_COMMON_EQUITY"
    OPERATING_ADR = "OPERATING_ADR"
    OPERATING_OTHER_EQUITY = "OPERATING_OTHER_EQUITY"
    ETF = "ETF"
    MUTUAL_OR_POOLED_FUND = "MUTUAL_OR_POOLED_FUND"
    CLOSED_END_FUND = "CLOSED_END_FUND"
    REIT_OR_SPECIAL_EQUITY = "REIT_OR_SPECIAL_EQUITY"
    PREFERRED_OR_HYBRID = "PREFERRED_OR_HYBRID"
    OTHER_13F_SECURITY = "OTHER_13F_SECURITY"
    NON_EQUITY_OR_UNSUPPORTED = "NON_EQUITY_OR_UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class ClassificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


OPERATING_TYPES = frozenset(
    {
        EconomicType.OPERATING_COMMON_EQUITY,
        EconomicType.OPERATING_ADR,
        EconomicType.OPERATING_OTHER_EQUITY,
    }
)

POOLED_TYPES = frozenset(
    {
        EconomicType.ETF,
        EconomicType.MUTUAL_OR_POOLED_FUND,
        EconomicType.CLOSED_END_FUND,
    }
)

# Exact-token pooled issuer markers (PROVISIONAL evidence).
POOLED_ISSUER_TOKENS = frozenset(
    {
        "TR", "TRUST", "FUND", "FUNDS", "FD", "FDS", "ETF", "SERIES", "SER",
        "PORTFOLIO",
    }
)

# Common-stock-like title_of_class markers (PROVISIONAL evidence).
COMMON_TITLES = frozenset(
    {
        "COM", "SHS", "ORD", "ORD SHS", "CL A", "CL B", "CL C", "CL A COM",
        "CAP STK CL A", "COMMON STOCK", "COM NEW", "CLASS A ORD SHS",
        "COMMON SHS",
    }
)


@dataclass(frozen=True)
class ClassificationResult:
    cusip: str
    economic_type: str
    classification_status: str
    classification_sources: tuple[str, ...] = ()
    classification_reason: str = ""
    classification_version: str = "v0.2.2"


def _tokens(value: str | None) -> list[str]:
    s = (value or "").upper()
    return [t for t in re.split(r"[^A-Z0-9]+", s) if t]


def is_pooled_issuer(issuer: str | None) -> bool:
    """Exact-token pooled-vehicle issuer test (no fuzzy matching)."""
    toks = _tokens(issuer)
    return any(t in POOLED_ISSUER_TOKENS for t in toks)


def title_has(title: str | None, *markers: str) -> bool:
    t = (title or "").upper()
    return any(m in t for m in markers)


def _of_set(of_records: list[dict], key: str) -> set[str]:
    return {str(r.get(key)) for r in of_records if r.get(key)}

