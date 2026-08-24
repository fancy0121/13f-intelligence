"""Resolution data models (no network, no side effects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ResolutionStatus(str, Enum):
    VERIFIED_EXACT = "VERIFIED_EXACT"
    VERIFIED_MULTI_SOURCE = "VERIFIED_MULTI_SOURCE"
    VERIFIED_HISTORICAL = "VERIFIED_HISTORICAL"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"
    NON_EQUITY_OR_UNSUPPORTED = "NON_EQUITY_OR_UNSUPPORTED"
    DELISTED_OR_TERMINATED = "DELISTED_OR_TERMINATED"
    HISTORICAL_IDENTITY_UNRESOLVED = "HISTORICAL_IDENTITY_UNRESOLVED"


VERIFIED_STATUSES = frozenset(
    {
        ResolutionStatus.VERIFIED_EXACT,
        ResolutionStatus.VERIFIED_MULTI_SOURCE,
        ResolutionStatus.VERIFIED_HISTORICAL,
    }
)


@dataclass(frozen=True)
class OpenFIGIRecord:
    figi: str | None = None
    compositeFIGI: str | None = None
    shareClassFIGI: str | None = None
    ticker: str | None = None
    exchCode: str | None = None
    securityType: str | None = None
    marketSector: str | None = None
    name: str | None = None
    securityDescription: str | None = None


@dataclass(frozen=True)
class OpenFIGIResponse:
    id_type: str
    id_value: str
    records: tuple[OpenFIGIRecord, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class InstrumentRecord:
    symbol: str
    exchange: str
    security_type: str | None
    figi: str | None
    composite_figi: str | None
    share_class_figi: str | None
    valid_from: str | None
    valid_to: str | None
    source: str
    status: str


@dataclass
class ResolutionResult:
    cusip: str
    issuer: str | None
    title_of_class: str | None
    status: str
    records: list[InstrumentRecord] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HistoricalSymbol:
    cusip: str
    symbol: str
    valid_from: str
    valid_to: str
    source: str
    notes: str = ""

