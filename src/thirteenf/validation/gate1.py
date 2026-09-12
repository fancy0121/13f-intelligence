"""Gate 1: independent reconciliation of preserved SEC rows to SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field

from thirteenf.database import connect_readonly
from thirteenf.validation.gate_context import (
    GateBundle,
    build_gate_context,
    component_bytes,
)
from thirteenf.validation.reference_xml import ReferenceXmlError, reference_rows
from thirteenf.validation.quarantine import audit_quarantine


@dataclass(frozen=True)
class Gate1Result:
    passed: bool
    checked_rows: int
    manager_ids: tuple[int, ...]
    mismatches: tuple[dict, ...]
    sampled_filings: tuple[dict, ...]
    quarantine: dict = field(default_factory=dict)


def run_gate1(
    bundle: GateBundle,
    *,
    managers: int = 5,
    quarters: int = 3,
    rows_per_filing: int = 10,
) -> Gate1Result:
    """Check exactly managers x quarters x rows against raw SEC XML."""
    if managers < 5 or quarters < 3 or rows_per_filing < 10:
        raise ValueError('Gate 1 requires at least 5 managers x 3 quarters x 10 rows')
    conn = connect_readonly(bundle.db_path, immutable=True)
    conn.row_factory = sqlite3.Row
    mismatches: list[dict] = []
    samples: list[dict] = []
    checked = 0
    quarantine = audit_quarantine(bundle)
    if quarantine["status"] != "PASS":
        mismatches.append({"kind": "source_quarantine", "detail": quarantine["errors"]})
    try:
        raw_fingerprint = build_gate_context(bundle).raw_fingerprint
        selected = _select_filings(
            conn,
            bundle.methodology_version,
            managers,
            quarters,
            rows_per_filing,
            raw_fingerprint,
        )
        selected_managers = tuple(sorted({int(row["manager_id"]) for row in selected}))
        if len(selected_managers) != managers or len(selected) != managers * quarters:
            mismatches.append(
                {
                    "kind": "sample_coverage",
                    "expected_managers": managers,
                    "actual_managers": len(selected_managers),
                    "expected_filings": managers * quarters,
                    "actual_filings": len(selected),
                }
            )

        for filing in selected:
            sample = {
                "manager_id": int(filing["manager_id"]),
                "report_period": filing["report_period"],
                "filing_id": int(filing["filing_id"]),
                "accession_number": filing["accession_number"],
                "form_type": filing["form_type"],
            }
            try:
                raw_rows = reference_rows(
                    component_bytes(
                        bundle,
                        int(filing["cik"]),
                        filing["accession_number"],
                        "information_table",
                    )
                )
            except (OSError, RuntimeError, ReferenceXmlError) as exc:
                samples.append(sample)
                mismatches.append(
                    {
                        "kind": "raw_document",
                        **sample,
                        "detail": str(exc),
                    }
                )
                continue
            if len(raw_rows) < rows_per_filing:
                mismatches.append(
                    {
                        "kind": "sample_coverage",
                        **sample,
                        "expected_rows": rows_per_filing,
                        "actual_rows": len(raw_rows),
                    }
                )
            db_rows = {
                int(row["row_ordinal"]): row
                for row in conn.execute(
                    """
                    SELECT row_ordinal, cusip, issuer, title_of_class, shares,
                           value, put_call, ssh_prnamt_type
                    FROM holdings WHERE filing_id=? ORDER BY row_ordinal
                    """,
                    (filing["filing_id"],),
                )
            }
            sampled_rows = sorted(
                raw_rows,
                key=lambda row: hashlib.sha256(
                    (
                        f"{raw_fingerprint}:{filing['accession_number']}:"
                        f"{row.row_ordinal}"
                    ).encode("utf-8")
                ).digest(),
            )[:rows_per_filing]
            sample["row_ordinals"] = [row.row_ordinal for row in sampled_rows]
            samples.append(sample)
            for raw in sampled_rows:
                checked += 1
                normalized = db_rows.get(raw.row_ordinal)
                if normalized is None:
                    mismatches.append(
                        {
                            "kind": "holding_row",
                            **sample,
                            "row_ordinal": raw.row_ordinal,
                            "field": "row",
                            "raw": "present",
                            "database": "missing",
                        }
                    )
                    continue
                comparisons = (
                    ("cusip", raw.cusip, normalized["cusip"]),
                    ("issuer", raw.issuer, normalized["issuer"]),
                    ("title_of_class", raw.title_of_class, normalized["title_of_class"]),
                    ("shares", raw.shares, normalized["shares"]),
                    ("value", raw.value, normalized["value"]),
                    ("put_call", raw.put_call, normalized["put_call"] or ""),
                    ("shares_type", raw.shares_type, normalized["ssh_prnamt_type"]),
                )
                for field, raw_value, db_value in comparisons:
                    if raw_value != db_value:
                        mismatches.append(
                            {
                                "kind": "holding_field",
                                **sample,
                                "row_ordinal": raw.row_ordinal,
                                "field": field,
                                "raw": raw_value,
                                "database": db_value,
                            }
                        )

        required = managers * quarters * rows_per_filing
        return Gate1Result(
            passed=not mismatches and checked == required,
            checked_rows=checked,
            manager_ids=selected_managers,
            mismatches=tuple(mismatches),
            sampled_filings=tuple(samples),
            quarantine=quarantine,
        )
    finally:
        conn.close()


def _select_filings(
    conn: sqlite3.Connection,
    methodology_version: str,
    manager_count: int,
    quarter_count: int,
    minimum_rows: int,
    raw_fingerprint: str,
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT ep.manager_id, ep.report_period, f.filing_id,
               f.accession_number, f.form_type, m.cik,
               COUNT(h.holding_id) AS holding_count,
               MAX(CASE WHEN f.is_amendment=1 THEN 1 ELSE 0 END) AS amendment,
               MAX(CASE WHEN h.put_call IN ('PUT','CALL') THEN 1 ELSE 0 END) AS option_row,
               MAX(CASE WHEN s.mapping_status='UNRESOLVED' THEN 1 ELSE 0 END) AS unresolved
        FROM effective_periods ep
        JOIN managers m ON m.manager_id=ep.manager_id
        JOIN effective_filing_components efc
          ON efc.effective_period_id=ep.effective_period_id
         AND efc.component_role='BASE'
        JOIN filings f ON f.filing_id=efc.filing_id
        LEFT JOIN holdings h ON h.filing_id=f.filing_id
        LEFT JOIN securities s ON s.cusip=h.cusip
        WHERE ep.methodology_version=? AND ep.status='READY'
        GROUP BY ep.manager_id, ep.report_period, f.filing_id,
                 f.accession_number, f.form_type, m.cik
        HAVING COUNT(h.holding_id)>=?
        ORDER BY ep.manager_id, ep.report_period DESC
        """,
        (methodology_version, minimum_rows),
    ).fetchall()
    by_manager: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        by_manager.setdefault(int(row["manager_id"]), []).append(row)
    eligible = [
        values[:quarter_count]
        for values in by_manager.values()
        if len(values) >= quarter_count
    ]
    eligible.sort(
        key=lambda values: (
            -max(int(row["amendment"]) for row in values),
            -max(int(row["option_row"]) for row in values),
            -max(int(row["unresolved"]) for row in values),
            hashlib.sha256(
                f"{raw_fingerprint}:{values[0]['manager_id']}".encode("utf-8")
            ).digest(),
        )
    )
    chosen = eligible[:manager_count]
    return [
        row
        for values in chosen
        for row in sorted(values, key=lambda item: item["report_period"])
    ]
