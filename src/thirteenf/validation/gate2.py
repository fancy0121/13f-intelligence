"""Gate 2: independent amendment replay, aggregation, and transition checks."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from thirteenf.database import connect_readonly
from thirteenf.validation.gate_context import (
    GateBundle,
    component_bytes,
    manifest_for,
)
from thirteenf.validation.reference_xml import (
    ReferenceCover,
    ReferenceXmlError,
    reference_cover,
    reference_rows,
)
from thirteenf.validation.quarantine import audit_quarantine


_CHANGE_TYPES = ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")
_FLOAT_TOLERANCE = 1e-12


@dataclass(frozen=True)
class Gate2Result:
    passed: bool
    checked_transitions: int
    manager_ids: tuple[int, ...]
    period_pairs: tuple[tuple[str, str], ...]
    mismatches: tuple[dict, ...]
    review_rows: tuple[dict, ...]
    quarantine: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _PeriodState:
    manager_id: int
    manager_name: str
    cik: int
    report_period: str
    positions: dict[tuple[int, str, str], dict]


def run_gate2(
    bundle: GateBundle,
    *,
    min_transitions: int = 30,
    min_managers: int = 5,
    effective_version: str = "v3",
) -> Gate2Result:
    """Independently replay raw filings and compare derived database state."""
    if min_transitions < 30 or min_managers < 5:
        raise ValueError('Gate 2 requires at least 30 transitions across 5 managers')
    conn = connect_readonly(bundle.db_path, immutable=True)
    conn.row_factory = sqlite3.Row
    mismatches: list[dict] = []
    quarantine = audit_quarantine(bundle)
    allowed_exclusions = set()
    if quarantine["status"] == "PASS":
        allowed_exclusions = {tuple(p) for p in quarantine["manager_periods"]}
    else:
        mismatches.append({"kind": "source_quarantine", "detail": quarantine["errors"]})
    try:
        periods = conn.execute(
            """
            SELECT ep.effective_period_id, ep.manager_id, m.name AS manager_name,
                   m.cik, ep.report_period, ep.status, ep.total_value
            FROM effective_periods ep
            JOIN managers m ON m.manager_id=ep.manager_id
            WHERE ep.methodology_version=?
            ORDER BY ep.manager_id, ep.report_period
            """,
            (bundle.methodology_version,),
        ).fetchall()
        expected_periods = set(conn.execute(
            "SELECT DISTINCT manager_id, report_period FROM filings WHERE ingest_status IN ('OK','QUARANTINED')"
        ).fetchall())
        expected_periods = {tuple(row) for row in expected_periods}
        actual_periods = {(p["manager_id"], p["report_period"]) for p in periods}
        if expected_periods != actual_periods:
            mismatches.append({
                "kind": "period_inventory",
                "missing": sorted(expected_periods - actual_periods),
                "unexpected": sorted(actual_periods - expected_periods),
            })
        if not periods:
            mismatches.append(
                {"kind": "coverage", "detail": "no effective periods found"}
            )

        period_records: list[tuple[sqlite3.Row, _PeriodState | None]] = []
        for period in periods:
            if (period["manager_id"], period["report_period"]) in allowed_exclusions:
                period_records.append((period, None))
                continue
            if period["status"] != "READY":
                mismatches.append(
                    {
                        "kind": "effective_period",
                        "manager_id": int(period["manager_id"]),
                        "report_period": period["report_period"],
                        "detail": f"status is {period['status']}, not READY",
                    }
                )
                period_records.append((period, None))
                continue
            state = _replay_period(conn, bundle, period, mismatches)
            period_records.append((period, state))

        expected, adjacent, period_pairs = _expected_changes(period_records)
        production = _production_changes(conn, bundle.methodology_version)
        _compare_change_sets(expected, production, mismatches)

        selected = _select_review_rows(
            conn,
            adjacent,
            production,
            min_transitions=min_transitions,
            min_managers=min_managers,
            methodology_version=bundle.methodology_version,
            effective_version=effective_version,
        )
        selected_managers = tuple(
            sorted({int(row["manager_id"]) for row in selected})
        )
        selected_types = {row["expected_change"] for row in selected}
        if len(selected) < min_transitions:
            mismatches.append(
                {
                    "kind": "coverage",
                    "detail": (
                        f"requires {min_transitions} adjacent transitions; "
                        f"found {len(selected)}"
                    ),
                }
            )
        if len(selected_managers) < min_managers:
            mismatches.append(
                {
                    "kind": "coverage",
                    "detail": (
                        f"requires {min_managers} managers; "
                        f"found {len(selected_managers)}"
                    ),
                }
            )
        missing_types = sorted(set(_CHANGE_TYPES) - selected_types)
        if missing_types:
            mismatches.append(
                {
                    "kind": "coverage",
                    "detail": f"missing change types: {', '.join(missing_types)}",
                }
            )
        return Gate2Result(
            passed=not mismatches,
            checked_transitions=len(selected),
            manager_ids=selected_managers,
            period_pairs=period_pairs,
            mismatches=tuple(mismatches),
            review_rows=tuple(selected),
            quarantine=quarantine,
        )
    finally:
        conn.close()


def _replay_period(
    conn: sqlite3.Connection,
    bundle: GateBundle,
    period: sqlite3.Row,
    mismatches: list[dict],
) -> _PeriodState | None:
    filings = conn.execute(
        """
        SELECT filing_id, accession_number, form_type, is_amendment,
               accepted_at, amendment_number, amendment_type,
               amendment_status, filing_date
        FROM filings
        WHERE manager_id=? AND report_period=? AND ingest_status='OK'
        ORDER BY COALESCE(accepted_at, ''), accession_number
        """,
        (period["manager_id"], period["report_period"]),
    ).fetchall()
    parsed: list[tuple[sqlite3.Row, ReferenceCover]] = []
    for filing in filings:
        identity = {
            "manager_id": int(period["manager_id"]),
            "report_period": period["report_period"],
            "accession_number": filing["accession_number"],
        }
        try:
            manifest = manifest_for(bundle, int(period["cik"]), filing["accession_number"])
            cover = reference_cover(
                component_bytes(
                    bundle,
                    int(period["cik"]),
                    filing["accession_number"],
                    "primary_document",
                )
            )
        except (OSError, RuntimeError, ReferenceXmlError) as exc:
            mismatches.append(
                {"kind": "raw_cover", **identity, "detail": str(exc)}
            )
            continue
        comparisons = (
            ("accepted_at", manifest.get("accepted_at"), filing["accepted_at"]),
            ("filing_date", manifest.get("filing_date"), filing["filing_date"]),
            ("report_period", cover.report_period, period["report_period"]),
            ("form_type", cover.submission_type, filing["form_type"]),
            ("is_amendment", int(cover.is_amendment), int(filing["is_amendment"])),
            ("amendment_number", cover.amendment_number, filing["amendment_number"]),
            ("amendment_type", cover.amendment_type, filing["amendment_type"]),
        )
        bad = False
        for field, raw_value, db_value in comparisons:
            if raw_value != db_value:
                bad = True
                mismatches.append(
                    {
                        "kind": "filing_metadata",
                        **identity,
                        "field": field,
                        "raw": raw_value,
                        "database": db_value,
                    }
                )
        expected_status = "PARSED" if cover.is_amendment else "NOT_APPLICABLE"
        if filing["amendment_status"] != expected_status:
            bad = True
            mismatches.append(
                {
                    "kind": "filing_metadata",
                    **identity,
                    "field": "amendment_status",
                    "raw": expected_status,
                    "database": filing["amendment_status"],
                }
            )
        if not filing["accepted_at"]:
            bad = True
            mismatches.append(
                {
                    "kind": "filing_metadata",
                    **identity,
                    "field": "accepted_at",
                    "detail": "missing",
                }
            )
        if not bad:
            parsed.append((filing, cover))
    if len(parsed) != len(filings) or not parsed:
        return None

    base: sqlite3.Row | None = None
    supplements: list[sqlite3.Row] = []
    last_amendment_number = 0
    for filing, cover in parsed:
        if not cover.is_amendment:
            if base is not None:
                mismatches.append(
                    {
                        "kind": "amendment_chain",
                        "manager_id": int(period["manager_id"]),
                        "report_period": period["report_period"],
                        "detail": "multiple original filings",
                    }
                )
                return None
            base = filing
            continue
        if base is None:
            mismatches.append(
                {
                    "kind": "amendment_chain",
                    "manager_id": int(period["manager_id"]),
                    "report_period": period["report_period"],
                    "detail": "amendment precedes original filing",
                }
            )
            return None
        number = int(cover.amendment_number or 0)
        if number <= last_amendment_number:
            mismatches.append(
                {
                    "kind": "amendment_chain",
                    "manager_id": int(period["manager_id"]),
                    "report_period": period["report_period"],
                    "detail": "amendment numbers are not strictly increasing",
                }
            )
            return None
        last_amendment_number = number
        if cover.amendment_type == "RESTATEMENT":
            base = filing
            supplements.clear()
        elif cover.amendment_type == "ADD_NEW_HOLDINGS":
            supplements.append(filing)
        else:
            mismatches.append(
                {
                    "kind": "amendment_chain",
                    "manager_id": int(period["manager_id"]),
                    "report_period": period["report_period"],
                    "detail": f"unsupported amendment {cover.amendment_type}",
                }
            )
            return None
    if base is None:
        mismatches.append(
            {
                "kind": "amendment_chain",
                "manager_id": int(period["manager_id"]),
                "report_period": period["report_period"],
                "detail": "no original or restated base filing",
            }
        )
        return None

    selected = [(base, "BASE", 0)] + [
        (filing, "SUPPLEMENT", sequence)
        for sequence, filing in enumerate(supplements, start=1)
    ]
    production_components = [
        (int(row["filing_id"]), row["component_role"], int(row["sequence"]))
        for row in conn.execute(
            """
            SELECT filing_id, component_role, sequence
            FROM effective_filing_components WHERE effective_period_id=?
            ORDER BY sequence
            """,
            (period["effective_period_id"],),
        )
    ]
    expected_components = [
        (int(filing["filing_id"]), role, sequence)
        for filing, role, sequence in selected
    ]
    if production_components != expected_components:
        mismatches.append(
            {
                "kind": "effective_component",
                "manager_id": int(period["manager_id"]),
                "report_period": period["report_period"],
                "raw": expected_components,
                "database": production_components,
            }
        )

    security_ids = {
        row["cusip"]: int(row["security_id"])
        for row in conn.execute("SELECT security_id, cusip FROM securities")
    }
    raw_positions: dict[tuple[str, str, str], dict] = {}
    for filing, _role, _sequence in selected:
        try:
            manifest = manifest_for(
                bundle,
                int(period["cik"]),
                filing["accession_number"],
            )
            info_component = (manifest.get("components") or {}).get(
                "information_table"
            )
            object_path = (
                str(info_component.get("object_path") or "")
                if isinstance(info_component, dict)
                else ""
            )
            rows = reference_rows(
                component_bytes(
                    bundle,
                    int(period["cik"]),
                    filing["accession_number"],
                    "information_table",
                )
            )
            # Independent unit interpretation uses the RAW manifest date, not
            # production aggregation helpers or the DB's derived values.
            date_text = manifest.get("filing_date")
            submitted = date.fromisoformat(date_text)
            if submitted.isoformat() != date_text:
                raise ReferenceXmlError("invalid filing date for value units")
            value_multiplier = 1000 if submitted < date(2023, 1, 3) else 1
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            mismatches.append(
                {
                    "kind": "raw_document",
                    "manager_id": int(period["manager_id"]),
                    "report_period": period["report_period"],
                    "accession_number": filing["accession_number"],
                    "detail": str(exc),
                }
            )
            return None
        for row in rows:
            key = (row.cusip, row.put_call, row.shares_type)
            record = raw_positions.setdefault(
                key,
                {"shares": 0, "value": 0, "provenance": []},
            )
            record["shares"] += row.shares
            record["value"] += row.value * value_multiplier
            record["provenance"].append(
                {
                    "filing_id": int(filing["filing_id"]),
                    "accession_number": filing["accession_number"],
                    "object_path": object_path,
                    "row_ordinal": row.row_ordinal,
                    "filing_date": date_text,
                    "value_basis": "USD_SEC_FILING_DATE_2023_01_03_V1",
                }
            )
    positions: dict[tuple[int, str, str], dict] = {}
    for raw_key, record in sorted(raw_positions.items()):
        security_id = security_ids.get(raw_key[0])
        if security_id is None:
            mismatches.append(
                {
                    "kind": "security_identity",
                    "manager_id": int(period["manager_id"]),
                    "report_period": period["report_period"],
                    "cusip": raw_key[0],
                    "detail": "CUSIP is absent from the security master",
                }
            )
            continue
        positions[(security_id, raw_key[1], raw_key[2])] = record
    total_value = sum(int(record["value"]) for record in positions.values())
    if positions and total_value <= 0:
        mismatches.append(
            {
                "kind": "effective_period",
                "manager_id": int(period["manager_id"]),
                "report_period": period["report_period"],
                "detail": "non-positive total value",
            }
        )
        return None
    for record in positions.values():
        record["weight"] = record["value"] / total_value if total_value else 0.0

    if int(period["total_value"] or 0) != total_value:
        mismatches.append(
            {
                "kind": "effective_period",
                "manager_id": int(period["manager_id"]),
                "report_period": period["report_period"],
                "field": "total_value",
                "raw": total_value,
                "database": period["total_value"],
            }
        )
    _compare_positions(conn, period, positions, mismatches)
    return _PeriodState(
        manager_id=int(period["manager_id"]),
        manager_name=period["manager_name"],
        cik=int(period["cik"]),
        report_period=period["report_period"],
        positions=positions,
    )


def _compare_positions(
    conn: sqlite3.Connection,
    period: sqlite3.Row,
    expected: dict[tuple[int, str, str], dict],
    mismatches: list[dict],
) -> None:
    production = {
        (int(row["security_id"]), row["put_call"], row["shares_type"]): row
        for row in conn.execute(
            """
            SELECT security_id, put_call, shares_type, shares, value,
                   portfolio_weight, provenance_json
            FROM effective_positions WHERE effective_period_id=?
            """,
            (period["effective_period_id"],),
        )
    }
    for key in sorted(set(expected) | set(production)):
        raw = expected.get(key)
        database = production.get(key)
        identity = {
            "kind": "effective_position",
            "manager_id": int(period["manager_id"]),
            "report_period": period["report_period"],
            "security_id": key[0],
            "put_call": key[1],
            "shares_type": key[2],
        }
        if raw is None or database is None:
            mismatches.append(
                {
                    **identity,
                    "field": "position",
                    "raw": "missing" if raw is None else "present",
                    "database": "missing" if database is None else "present",
                }
            )
            continue
        raw_provenance = [
            {
                "filing_id": item["filing_id"],
                "row_ordinal": item["row_ordinal"],
                "filing_date": item["filing_date"],
                "value_basis": item["value_basis"],
            }
            for item in raw["provenance"]
        ]
        try:
            database_provenance = json.loads(database["provenance_json"])
        except (TypeError, json.JSONDecodeError):
            database_provenance = "INVALID_JSON"
        comparisons = (
            ("shares", raw["shares"], database["shares"], False),
            ("value", raw["value"], database["value"], False),
            ("portfolio_weight", raw["weight"], database["portfolio_weight"], True),
            ("provenance", raw_provenance, database_provenance, False),
        )
        for field, raw_value, db_value, floating in comparisons:
            equal = _float_equal(raw_value, db_value) if floating else raw_value == db_value
            if not equal:
                mismatches.append(
                    {
                        **identity,
                        "field": field,
                        "raw": raw_value,
                        "database": db_value,
                    }
                )


def _expected_changes(period_records):
    by_manager: dict[int, list[tuple[sqlite3.Row, _PeriodState | None]]] = {}
    for period, state in period_records:
        by_manager.setdefault(int(period["manager_id"]), []).append((period, state))
    expected: dict[tuple[int, int, str, str, str], dict] = {}
    adjacent: list[dict] = []
    pair_set: set[tuple[str, str]] = set()
    for manager_id, records in sorted(by_manager.items()):
        seen_period = False
        previous: _PeriodState | None = None
        for period, state in records:
            report_period = period["report_period"]
            if state is None:
                seen_period = True
                previous = None
                continue
            if seen_period and previous is not None and _is_next_quarter(
                previous.report_period, report_period
            ):
                pair_set.add((previous.report_period, report_period))
                for key in sorted(set(previous.positions) | set(state.positions)):
                    change = _change_record(
                        state,
                        key,
                        previous.positions.get(key),
                        state.positions.get(key),
                        previous_period=previous.report_period,
                    )
                    expected[change["key"]] = change
                    adjacent.append(change)
            seen_period = True
            previous = state
    return expected, adjacent, tuple(sorted(pair_set))


def _change_record(state, key, previous, current, *, previous_period):
    if previous is None:
        change_type = "NEW"
    elif current is None:
        change_type = "EXIT"
    elif current["shares"] > previous["shares"]:
        change_type = "ADD"
    elif current["shares"] < previous["shares"]:
        change_type = "REDUCE"
    else:
        change_type = "UNCHANGED"
    shares_prev = previous["shares"] if previous else None
    shares_now = current["shares"] if current else None
    weight_prev = previous["weight"] if previous else None
    weight_now = current["weight"] if current else None
    share_change = None
    share_change_pct = None
    if shares_prev is not None and shares_now is not None:
        share_change = shares_now - shares_prev
        if shares_prev != 0:
            share_change_pct = share_change / shares_prev
    weight_change = None
    if weight_prev is not None and weight_now is not None:
        weight_change = weight_now - weight_prev
    return {
        "key": (state.manager_id, key[0], key[1], key[2], state.report_period),
        "manager_id": state.manager_id,
        "manager_name": state.manager_name,
        "security_id": key[0],
        "put_call": key[1],
        "shares_type": key[2],
        "prev_period": previous_period,
        "report_period": state.report_period,
        "change_type": change_type,
        "shares_prev": shares_prev,
        "shares_now": shares_now,
        "share_change": share_change,
        "share_change_pct": share_change_pct,
        "weight_prev": weight_prev,
        "weight_now": weight_now,
        "weight_change": weight_change,
        "prev_provenance": previous["provenance"] if previous else [],
        "now_provenance": current["provenance"] if current else [],
    }


def _production_changes(conn, methodology_version):
    return {
        (
            int(row["manager_id"]),
            int(row["security_id"]),
            row["put_call"],
            row["shares_type"],
            row["report_period"],
        ): row
        for row in conn.execute(
            """
            SELECT manager_id, security_id, put_call, shares_type,
                   report_period, change_type, shares_prev, shares_now,
                   share_change, share_change_pct, weight_prev, weight_now,
                   weight_change
            FROM position_changes WHERE methodology_version=?
            """,
            (methodology_version,),
        )
    }


def _compare_change_sets(expected, production, mismatches):
    for key in sorted(set(expected) | set(production)):
        raw = expected.get(key)
        database = production.get(key)
        identity = {
            "kind": "position_change",
            "manager_id": key[0],
            "security_id": key[1],
            "put_call": key[2],
            "shares_type": key[3],
            "report_period": key[4],
        }
        if raw is None or database is None:
            mismatches.append(
                {
                    **identity,
                    "field": "transition",
                    "raw": "missing" if raw is None else "present",
                    "database": "missing" if database is None else "present",
                }
            )
            continue
        fields = (
            ("change_type", raw["change_type"], database["change_type"], False),
            ("shares_prev", raw["shares_prev"], database["shares_prev"], False),
            ("shares_now", raw["shares_now"], database["shares_now"], False),
            ("share_change", raw["share_change"], database["share_change"], False),
            (
                "share_change_pct",
                raw["share_change_pct"],
                database["share_change_pct"],
                True,
            ),
            ("weight_prev", raw["weight_prev"], database["weight_prev"], True),
            ("weight_now", raw["weight_now"], database["weight_now"], True),
            ("weight_change", raw["weight_change"], database["weight_change"], True),
        )
        for field, raw_value, db_value, floating in fields:
            equal = _float_equal(raw_value, db_value) if floating else raw_value == db_value
            if not equal:
                mismatches.append(
                    {
                        **identity,
                        "field": field,
                        "raw": raw_value,
                        "database": db_value,
                    }
                )


def _select_review_rows(
    conn,
    adjacent,
    production,
    *,
    min_transitions,
    min_managers,
    methodology_version,
    effective_version,
):
    ordered = sorted(
        adjacent,
        key=lambda row: (
            row["manager_id"],
            row["report_period"],
            _CHANGE_TYPES.index(row["change_type"]),
            row["security_id"],
            row["put_call"],
            row["shares_type"],
        ),
    )
    selected: list[dict] = []
    selected_keys: set[tuple] = set()

    def add(candidate):
        if candidate["key"] not in selected_keys:
            selected_keys.add(candidate["key"])
            selected.append(candidate)

    for manager_id in sorted({row["manager_id"] for row in ordered})[:min_managers]:
        candidate = next(row for row in ordered if row["manager_id"] == manager_id)
        add(candidate)
    # Preserve meaningful controls while avoiding a sample dominated by the
    # largest manager or most common classification.
    quotas = {"NEW": 5, "ADD": 5, "REDUCE": 5, "EXIT": 5, "UNCHANGED": 3}
    for change_type in _CHANGE_TYPES:
        candidates = [
            row for row in ordered if row["change_type"] == change_type
        ][: quotas[change_type]]
        for candidate in candidates:
            add(candidate)
    divergence = [
        row
        for row in ordered
        if row["change_type"] == "ADD"
        and row["shares_prev"] is not None
        and row["shares_now"] is not None
        and row["shares_now"] > row["shares_prev"]
        and row["weight_prev"] is not None
        and row["weight_now"] is not None
        and row["weight_now"] < row["weight_prev"]
    ]
    for candidate in divergence[:2]:
        add(candidate)
    for pair in sorted({(row["prev_period"], row["report_period"]) for row in ordered}):
        candidate = next(
            row
            for row in ordered
            if (row["prev_period"], row["report_period"]) == pair
        )
        add(candidate)
    for candidate in ordered:
        if len(selected) >= min_transitions:
            break
        add(candidate)

    securities = {
        int(row["security_id"]): row["cusip"]
        for row in conn.execute("SELECT security_id, cusip FROM securities")
    }
    rows = []
    for candidate in selected:
        prod = production.get(candidate["key"])
        transition_id = "T-" + hashlib.sha256(
            (
                ":".join(str(value) for value in candidate["key"])
                + f":{methodology_version}"
            ).encode("utf-8")
        ).hexdigest()[:20]
        rows.append(
            {
                "transition_id": transition_id,
                "manager_id": candidate["manager_id"],
                "manager_name": candidate["manager_name"],
                "prev_period": candidate["prev_period"],
                "report_period": candidate["report_period"],
                "security_id": candidate["security_id"],
                "cusip": securities.get(candidate["security_id"], ""),
                "put_call": candidate["put_call"],
                "shares_type": candidate["shares_type"],
                "expected_change": candidate["change_type"],
                "expected_shares_prev": candidate["shares_prev"],
                "expected_shares_now": candidate["shares_now"],
                "expected_weight_prev": candidate["weight_prev"],
                "expected_weight_now": candidate["weight_now"],
                "production_change": prod["change_type"] if prod else None,
                "production_shares_prev": prod["shares_prev"] if prod else None,
                "production_shares_now": prod["shares_now"] if prod else None,
                "production_weight_prev": prod["weight_prev"] if prod else None,
                "production_weight_now": prod["weight_now"] if prod else None,
                "raw_provenance": json.dumps(
                    {
                        "previous": candidate["prev_provenance"],
                        "current": candidate["now_provenance"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "human_result": "",
                "reviewer": "",
                "review_date": "",
                "methodology_version": methodology_version,
                "effective_version": effective_version,
                "reviewer_notes": "",
            }
        )
    return rows


def _float_equal(first, second) -> bool:
    if first is None or second is None:
        return first is second
    try:
        return math.isclose(
            float(first),
            float(second),
            rel_tol=_FLOAT_TOLERANCE,
            abs_tol=_FLOAT_TOLERANCE,
        )
    except (TypeError, ValueError):
        return False


def _is_next_quarter(previous: str, current: str) -> bool:
    previous_date = date.fromisoformat(previous)
    current_date = date.fromisoformat(current)
    previous_index = previous_date.year * 4 + (previous_date.month - 1) // 3
    current_index = current_date.year * 4 + (current_date.month - 1) // 3
    return current_index == previous_index + 1
