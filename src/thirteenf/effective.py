"""Deterministic amendment selection and economic-position aggregation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from thirteenf.parser import AmendmentType


class AmendmentPendingError(ValueError):
    """Raised when amendment semantics are missing or contradictory."""


class EffectiveDataError(ValueError):
    """Raised when a filing chain cannot form an effective state."""


@dataclass(frozen=True)
class FilingVersion:
    filing_id: int
    accession_number: str
    accepted_at: str
    amendment_number: int | None
    amendment_type: AmendmentType | None
    is_amendment: bool = False


@dataclass(frozen=True)
class EffectiveSelection:
    base_filing_id: int
    supplement_filing_ids: tuple[int, ...]
    state_hash: str


@dataclass(frozen=True)
class EffectivePosition:
    effective_period_id: int
    security_id: int
    put_call: str
    shares_type: str
    shares: int
    value: int
    portfolio_weight: float
    provenance: tuple[tuple[int, int], ...]


def select_effective_components(
    versions: list[FilingVersion],
) -> EffectiveSelection:
    """Replay one manager/quarter filing chain without touching raw rows."""

    if not versions:
        raise EffectiveDataError("filing chain is empty")
    ordered = sorted(
        versions,
        key=lambda item: (
            item.accepted_at,
            item.amendment_number or 0,
            item.accession_number,
        ),
    )
    base_filing_id: int | None = None
    supplements: list[int] = []
    amendment_numbers: set[int] = set()
    last_amendment_number = 0

    for version in ordered:
        if not version.accepted_at:
            raise EffectiveDataError(
                f"filing {version.accession_number} is missing accepted_at"
            )
        if not version.is_amendment:
            if version.amendment_number is not None or version.amendment_type is not None:
                raise AmendmentPendingError(
                    f"base filing {version.accession_number} has amendment metadata"
                )
            if base_filing_id is not None:
                raise EffectiveDataError("multiple original filings in one period")
            base_filing_id = version.filing_id
            continue

        if version.amendment_number is None or version.amendment_type is None:
            raise AmendmentPendingError(
                f"amendment {version.accession_number} has incomplete metadata"
            )
        number = version.amendment_number
        if number < 1 or number in amendment_numbers or number <= last_amendment_number:
            raise AmendmentPendingError(
                f"amendment {version.accession_number} has invalid sequence"
            )
        amendment_numbers.add(number)
        last_amendment_number = number
        if base_filing_id is None:
            raise AmendmentPendingError("amendment has no preceding base filing")

        if version.amendment_type is AmendmentType.RESTATEMENT:
            base_filing_id = version.filing_id
            supplements.clear()
        elif version.amendment_type is AmendmentType.ADD_NEW_HOLDINGS:
            supplements.append(version.filing_id)
        else:
            raise AmendmentPendingError(
                f"amendment {version.accession_number} has unsupported metadata"
            )

    if base_filing_id is None:
        raise EffectiveDataError("filing chain has no usable base filing")
    return EffectiveSelection(
        base_filing_id=base_filing_id,
        supplement_filing_ids=tuple(supplements),
        state_hash=_versions_hash(ordered),
    )


def rebuild_effective_positions(
    conn: sqlite3.Connection,
    methodology_version: str,
) -> int:
    """Rebuild effective positions for every ingested manager/quarter."""

    conn.execute("SAVEPOINT rebuild_effective")
    inserted = 0
    try:
        conn.execute(
            "DELETE FROM effective_periods WHERE methodology_version=?",
            (methodology_version,),
        )
        periods = conn.execute(
            """
            SELECT manager_id, report_period
            FROM filings
            WHERE ingest_status='OK'
            GROUP BY manager_id, report_period
            ORDER BY manager_id, report_period
            """
        ).fetchall()
        for manager_id, report_period in periods:
            filing_rows = conn.execute(
                """
                SELECT filing_id, accession_number, accepted_at,
                       amendment_number, amendment_type, is_amendment,
                       amendment_status, raw_checksum
                FROM filings
                WHERE manager_id=? AND report_period=? AND ingest_status='OK'
                ORDER BY COALESCE(accepted_at, ''), filing_date,
                         accession_number
                """,
                (manager_id, report_period),
            ).fetchall()
            versions, metadata_pending = _filing_versions(filing_rows)
            all_state_hash = _period_state_hash(
                methodology_version, filing_rows
            )
            if metadata_pending:
                _insert_effective_period(
                    conn,
                    manager_id=manager_id,
                    report_period=report_period,
                    methodology_version=methodology_version,
                    state_hash=all_state_hash,
                    status="AMENDMENT_PENDING",
                    total_value=None,
                )
                continue
            try:
                selection = select_effective_components(versions)
            except AmendmentPendingError:
                _insert_effective_period(
                    conn,
                    manager_id=manager_id,
                    report_period=report_period,
                    methodology_version=methodology_version,
                    state_hash=all_state_hash,
                    status="AMENDMENT_PENDING",
                    total_value=None,
                )
                continue
            except EffectiveDataError:
                _insert_effective_period(
                    conn,
                    manager_id=manager_id,
                    report_period=report_period,
                    methodology_version=methodology_version,
                    state_hash=all_state_hash,
                    status="INCOMPLETE",
                    total_value=None,
                )
                continue

            component_ids = (
                selection.base_filing_id,
                *selection.supplement_filing_ids,
            )
            raw_rows = _load_component_rows(conn, component_ids)
            if raw_rows is None:
                _insert_effective_period(
                    conn,
                    manager_id=manager_id,
                    report_period=report_period,
                    methodology_version=methodology_version,
                    state_hash=all_state_hash,
                    status="INCOMPLETE",
                    total_value=None,
                )
                continue
            aggregates = _aggregate_rows(raw_rows)
            total_value = sum(record["value"] for record in aggregates.values())
            if aggregates and total_value <= 0:
                _insert_effective_period(
                    conn,
                    manager_id=manager_id,
                    report_period=report_period,
                    methodology_version=methodology_version,
                    state_hash=all_state_hash,
                    status="INCOMPLETE",
                    total_value=None,
                )
                continue

            effective_period_id = _insert_effective_period(
                conn,
                manager_id=manager_id,
                report_period=report_period,
                methodology_version=methodology_version,
                state_hash=_selected_state_hash(
                    methodology_version,
                    selection,
                    filing_rows,
                ),
                status="READY",
                total_value=total_value,
            )
            conn.execute(
                """
                INSERT INTO effective_filing_components(
                    effective_period_id, filing_id, component_role, sequence
                ) VALUES (?, ?, 'BASE', 0)
                """,
                (effective_period_id, selection.base_filing_id),
            )
            for sequence, filing_id in enumerate(
                selection.supplement_filing_ids, start=1
            ):
                conn.execute(
                    """
                    INSERT INTO effective_filing_components(
                        effective_period_id, filing_id, component_role, sequence
                    ) VALUES (?, ?, 'SUPPLEMENT', ?)
                    """,
                    (effective_period_id, filing_id, sequence),
                )

            for key in sorted(aggregates):
                record = aggregates[key]
                provenance_json = json.dumps(
                    [
                        {"filing_id": filing_id, "row_ordinal": row_ordinal}
                        for filing_id, row_ordinal in record["provenance"]
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                )
                conn.execute(
                    """
                    INSERT INTO effective_positions(
                        effective_period_id, manager_id, report_period,
                        security_id, put_call, shares_type, shares, value,
                        portfolio_weight, provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        effective_period_id,
                        manager_id,
                        report_period,
                        key[0],
                        key[1],
                        key[2],
                        record["shares"],
                        record["value"],
                        record["value"] / total_value,
                        provenance_json,
                    ),
                )
                inserted += 1
        conn.execute("RELEASE SAVEPOINT rebuild_effective")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT rebuild_effective")
        conn.execute("RELEASE SAVEPOINT rebuild_effective")
        raise
    return inserted


def load_effective_positions(
    conn: sqlite3.Connection,
    manager_id: int,
    report_period: str,
    methodology_version: str | None = None,
) -> dict[tuple[int, str, str], EffectivePosition]:
    """Load one READY effective period without collapsing position types."""

    params: list[object] = [manager_id, report_period]
    where_version = ""
    if methodology_version is not None:
        where_version = " AND methodology_version=?"
        params.append(methodology_version)
    periods = conn.execute(
        f"""
        SELECT effective_period_id
        FROM effective_periods
        WHERE manager_id=? AND report_period=? AND status='READY'
        {where_version}
        ORDER BY methodology_version
        """,
        params,
    ).fetchall()
    if not periods:
        return {}
    if len(periods) != 1:
        raise EffectiveDataError(
            "multiple methodology versions match; specify methodology_version"
        )
    return _load_effective_position_map(conn, periods[0][0])


def _load_effective_position_map(
    conn: sqlite3.Connection,
    effective_period_id: int,
) -> dict[tuple[int, str, str], EffectivePosition]:
    rows = conn.execute(
        """
        SELECT security_id, put_call, shares_type, shares, value,
               portfolio_weight, provenance_json
        FROM effective_positions
        WHERE effective_period_id=?
        ORDER BY security_id, put_call, shares_type
        """,
        (effective_period_id,),
    ).fetchall()
    result: dict[tuple[int, str, str], EffectivePosition] = {}
    for security_id, put_call, shares_type, shares, value, weight, raw in rows:
        provenance = tuple(
            (int(item["filing_id"]), int(item["row_ordinal"]))
            for item in json.loads(raw)
        )
        key = (security_id, put_call, shares_type)
        result[key] = EffectivePosition(
            effective_period_id=effective_period_id,
            security_id=security_id,
            put_call=put_call,
            shares_type=shares_type,
            shares=shares,
            value=value,
            portfolio_weight=weight,
            provenance=provenance,
        )
    return result


def _filing_versions(rows) -> tuple[list[FilingVersion], bool]:
    versions: list[FilingVersion] = []
    pending = False
    for row in rows:
        (
            filing_id,
            accession,
            accepted_at,
            amendment_number,
            amendment_type,
            is_amendment,
            amendment_status,
            _raw_checksum,
        ) = row
        normalized_type = None
        if amendment_type:
            try:
                normalized_type = AmendmentType(amendment_type)
            except ValueError:
                pending = True
        if is_amendment and (
            amendment_status != "PARSED"
            or amendment_number is None
            or normalized_type is None
        ):
            pending = True
        versions.append(
            FilingVersion(
                filing_id=filing_id,
                accession_number=accession,
                accepted_at=accepted_at or "",
                amendment_number=amendment_number,
                amendment_type=normalized_type,
                is_amendment=bool(is_amendment),
            )
        )
    return versions, pending


def _load_component_rows(conn, filing_ids: tuple[int, ...]):
    placeholders = ",".join("?" for _ in filing_ids)
    rows = conn.execute(
        f"""
        SELECT h.filing_id, h.row_ordinal, s.security_id, h.put_call,
               h.ssh_prnamt_type, h.shares, h.value
        FROM holdings h
        LEFT JOIN securities s ON s.cusip=h.cusip
        WHERE h.filing_id IN ({placeholders})
        ORDER BY h.filing_id, h.row_ordinal
        """,
        filing_ids,
    ).fetchall()
    for row in rows:
        _, _, security_id, put_call, shares_type, shares, value = row
        if (
            security_id is None
            or put_call not in {"", "CALL", "PUT"}
            or shares_type not in {"SH", "PRN"}
            or not _is_nonnegative_integer(shares)
            or not _is_nonnegative_integer(value)
        ):
            return None
    return rows


def _aggregate_rows(rows) -> dict[tuple[int, str, str], dict]:
    aggregates: dict[tuple[int, str, str], dict] = {}
    for (
        filing_id,
        row_ordinal,
        security_id,
        put_call,
        shares_type,
        shares,
        value,
    ) in rows:
        key = (security_id, put_call, shares_type)
        record = aggregates.setdefault(
            key,
            {"shares": 0, "value": 0, "provenance": []},
        )
        record["shares"] += int(shares)
        record["value"] += int(value)
        record["provenance"].append((filing_id, row_ordinal))
    return aggregates


def _is_nonnegative_integer(value) -> bool:
    return (
        value is not None
        and not isinstance(value, bool)
        and int(value) == value
        and int(value) >= 0
    )


def _insert_effective_period(
    conn,
    *,
    manager_id,
    report_period,
    methodology_version,
    state_hash,
    status,
    total_value,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO effective_periods(
            manager_id, report_period, methodology_version, state_hash,
            status, total_value
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            manager_id,
            report_period,
            methodology_version,
            state_hash,
            status,
            total_value,
        ),
    )
    return int(cursor.lastrowid)


def _versions_hash(versions: list[FilingVersion]) -> str:
    payload = [
        {
            "accession_number": item.accession_number,
            "accepted_at": item.accepted_at,
            "amendment_number": item.amendment_number,
            "amendment_type": (
                item.amendment_type.value if item.amendment_type else None
            ),
            "is_amendment": item.is_amendment,
        }
        for item in versions
    ]
    return _hash_payload(payload)


def _period_state_hash(methodology_version: str, filing_rows) -> str:
    return _hash_payload(
        {
            "methodology_version": methodology_version,
            "filings": [tuple(row)[1:] for row in filing_rows],
        }
    )


def _selected_state_hash(
    methodology_version: str,
    selection: EffectiveSelection,
    filing_rows,
) -> str:
    identities = {row[0]: (row[1], row[7]) for row in filing_rows}
    ids = (selection.base_filing_id, *selection.supplement_filing_ids)
    return _hash_payload(
        {
            "methodology_version": methodology_version,
            "selection_hash": selection.state_hash,
            "components": [
                {
                    "accession_number": identities[filing_id][0],
                    "raw_checksum": identities[filing_id][1],
                }
                for filing_id in ids
            ],
        }
    )


def _hash_payload(payload) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
