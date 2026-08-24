"""Deterministic CUSIP -> market instrument resolution engine (pure logic).

No network. No future returns. No LLM. No fuzzy issuer-only acceptance.
Implements the frozen protocol research/security_resolution_protocol_v0.2.1.md.
"""

from __future__ import annotations

from thirteenf.research.resolution.models import (
    InstrumentRecord,
    OpenFIGIResponse,
    ResolutionResult,
    ResolutionStatus,
    VERIFIED_STATUSES,
)
from thirteenf.research.resolution.sources import (
    SECIndex,
    distinct_us_tickers,
    names_match,
    us_filter,
)


def _result(cusip, issuer, title_of_class, status, records=None, sources=None, notes=None):
    return ResolutionResult(
        cusip=cusip,
        issuer=issuer,
        title_of_class=title_of_class,
        status=status,
        records=records or [],
        sources=sources or [],
        notes=notes or [],
    )


def _check_adr_consistency(title_of_class: str | None, sec_types: set[str]) -> str | None:
    """Return a conflict note, or None when consistent.

    'ADS' (American Depositary Shares) is treated as an ADR marker (TSM/PDD
    filings use 'SPONSORED ADS'). A missing ADR marker in title_of_class is a
    note, not a conflict, because filers commonly omit it (e.g. 'COM').
    """
    t = (title_of_class or "").upper()
    is_adr = ("ADR" in t) or ("ADS" in t)
    of_is_adr = "ADR" in sec_types
    if t and is_adr and not of_is_adr:
        return f"13F title_of_class declares ADR but OpenFIGI securityType={sorted(sec_types)}"
    return None


def resolve_cusip(
    cusip: str,
    issuer: str | None,
    title_of_class: str | None,
    of_response: OpenFIGIResponse | None,
    sec_index: SECIndex | None,
    historical_map: dict[str, list],
) -> ResolutionResult:
    """Resolve one CUSIP to market instruments per the frozen protocol."""
    notes: list[str] = []
    sources: list[str] = []
    records: list[InstrumentRecord] = []

    # Curated historical symbols (Tier 4), if any.
    hist = historical_map.get(cusip, []) if historical_map else []
    for h in hist:
        records.append(
            InstrumentRecord(
                symbol=h.symbol,
                exchange="",
                security_type=None,
                figi=None,
                composite_figi=None,
                share_class_figi=None,
                valid_from=h.valid_from,
                valid_to=h.valid_to,
                source=h.source,
                status=ResolutionStatus.VERIFIED_HISTORICAL.value,
            )
        )
        sources.append("historical_curated")

    # OpenFIGI path (Rule C / Rule A).
    if of_response is not None and not of_response.error and of_response.records:
        records_all = of_response.records
        scf = {r.shareClassFIGI for r in records_all if r.shareClassFIGI}
        sectors = {r.marketSector for r in records_all if r.marketSector}
        sec_types = {r.securityType for r in records_all if r.securityType}
        if len(scf) > 1:
            return _result(
                cusip, issuer, title_of_class,
                ResolutionStatus.CONFLICT.value,
                records=records,
                sources=sources,
                notes=notes + [f"multiple shareClassFIGI for one CUSIP: {sorted(scf)}"],
            )
        if sectors and sectors != {"Equity"}:
            return _result(
                cusip, issuer, title_of_class,
                ResolutionStatus.NON_EQUITY_OR_UNSUPPORTED.value,
                records=records,
                sources=sources,
                notes=notes + [f"marketSector={sorted(sectors)} not Equity"],
            )
        us_tickers = distinct_us_tickers(records_all)
        if not us_tickers:
            return _result(
                cusip, issuer, title_of_class,
                ResolutionStatus.UNRESOLVED.value,
                records=records,
                sources=sources,
                notes=notes + [
                    "no US venue record (possibly delisted/terminated or wrong CUSIP)"
                ],
            )
        if len(us_tickers) > 1:
            return _result(
                cusip, issuer, title_of_class,
                ResolutionStatus.AMBIGUOUS.value,
                records=records,
                sources=sources,
                notes=notes + [f"multiple distinct US tickers: {us_tickers}"],
            )
        symbol = us_tickers[0]
        us_records = [r for r in us_filter(records_all) if r.ticker == symbol]
        rep = us_records[0]

        adr_note = _check_adr_consistency(title_of_class, sec_types)
        if adr_note:
            return _result(
                cusip, issuer, title_of_class,
                ResolutionStatus.CONFLICT.value,
                records=records,
                sources=sources,
                notes=notes + [adr_note],
            )

        # SEC issuer corroboration (Rule C requirement 4).
        corroborated = False
        if issuer and names_match(rep.name, issuer):
            corroborated = True
            sources.append("sec_13f_issuer")
        # Fund/trust filings carry the issuer as the trust; the specific fund
        # name appears in title_of_class (also SEC-derived filing text).
        if not corroborated and title_of_class and names_match(rep.name, title_of_class):
            corroborated = True
            sources.append("sec_13f_title_of_class")
        if sec_index is not None:
            sec_recs = sec_index.lookup(issuer) if issuer else []
            if sec_recs:
                if any(names_match(r.get("title"), issuer) or names_match(r.get("title"), rep.name) for r in sec_recs):
                    corroborated = True
                    sources.append("sec_ticker_file")
                # SEC issuer set contains the OpenFIGI symbol (e.g., TSM in
                # {TSM, TSMWF} for Taiwan Semiconductor) -> corroboration.
                sec_issuer_tickers = {r.get("ticker") for r in sec_recs if r.get("ticker")}
                if not corroborated and symbol in sec_issuer_tickers:
                    corroborated = True
                    sources.append("sec_ticker_file")
                sec_unique = sec_index.unique_ticker(issuer)
                if sec_unique is not None and sec_unique != symbol:
                    return _result(
                        cusip, issuer, title_of_class,
                        ResolutionStatus.CONFLICT.value,
                        records=records,
                        sources=sources,
                        notes=notes + [f"SEC unique ticker {sec_unique} != OpenFIGI {symbol}"],
                    )
            # SEC title (fund name) corroboration: SEC ticker file often holds
            # the full fund name which matches OpenFIGI's returned name.
            sec_title_tickers = sec_index.ticker_set_for_title(rep.name) if rep.name else set()
            if sec_title_tickers:
                if symbol in sec_title_tickers:
                    if not corroborated:
                        corroborated = True
                        sources.append("sec_ticker_file")
                elif len(sec_title_tickers) == 1:
                    # A unique SEC fund title maps to a different ticker.
                    return _result(
                        cusip, issuer, title_of_class,
                        ResolutionStatus.CONFLICT.value,
                        records=records,
                        sources=sources,
                        notes=notes + [
                            f"SEC title '{rep.name}' -> {sorted(sec_title_tickers)} != OpenFIGI {symbol}"
                        ],
                    )
        if not corroborated:
            return _result(
                cusip, issuer, title_of_class,
                ResolutionStatus.UNRESOLVED.value,
                records=records,
                sources=sources,
                notes=notes + ["OpenFIGI candidate but no SEC issuer corroboration"],
            )

        records.append(
            InstrumentRecord(
                symbol=symbol,
                exchange="US",
                security_type=sorted(sec_types)[0] if sec_types else None,
                figi=rep.figi,
                composite_figi=rep.compositeFIGI,
                share_class_figi=rep.shareClassFIGI,
                valid_from=None,
                valid_to=None,
                source="openfigi" + ("+sec" if sec_index is not None and sec_index.lookup(issuer) else "+13f"),
                status=ResolutionStatus.VERIFIED_EXACT.value,
            )
        )
        if "openfigi" not in sources:
            sources.append("openfigi")
        if hist:
            status = ResolutionStatus.VERIFIED_HISTORICAL.value
        else:
            sec_agree = False
            if sec_index is not None:
                if sec_index.unique_ticker(issuer) == symbol:
                    sec_agree = True
                else:
                    title_tickers = sec_index.ticker_set_for_title(rep.name) if rep.name else set()
                    if title_tickers and len(title_tickers) == 1 and symbol in title_tickers:
                        sec_agree = True
            status = (
                ResolutionStatus.VERIFIED_MULTI_SOURCE.value
                if sec_agree
                else ResolutionStatus.VERIFIED_EXACT.value
            )
        return _result(
            cusip, issuer, title_of_class, status,
            records=records, sources=sources, notes=notes,
        )

    if of_response is not None and of_response.error:
        notes.append(f"openfigi error: {of_response.error}")

    # Rule B: SEC direct evidence, OpenFIGI unavailable.
    if sec_index is not None and issuer:
        sec_recs = sec_index.lookup(issuer)
        if sec_recs:
            sec_unique = sec_index.unique_ticker(issuer)
            if sec_unique is not None:
                records.append(
                    InstrumentRecord(
                        symbol=sec_unique,
                        exchange="",
                        security_type=None,
                        figi=None,
                        composite_figi=None,
                        share_class_figi=None,
                        valid_from=None,
                        valid_to=None,
                        source="sec",
                        status=ResolutionStatus.VERIFIED_EXACT.value,
                    )
                )
                return _result(
                    cusip, issuer, title_of_class,
                    ResolutionStatus.VERIFIED_EXACT.value,
                    records=records, sources=["sec"], notes=notes,
                )
            return _result(
                cusip, issuer, title_of_class,
                ResolutionStatus.AMBIGUOUS.value,
                records=records,
                sources=["sec"],
                notes=notes + ["SEC issuer matched but multiple tickers; OpenFIGI unavailable"],
            )

    return _result(
        cusip, issuer, title_of_class,
        ResolutionStatus.UNRESOLVED.value,
        records=records, sources=sources, notes=notes,
    )


def is_verified_status(status: str) -> bool:
    return status in VERIFIED_STATUSES
