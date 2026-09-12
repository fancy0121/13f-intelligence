from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.normalization import normalize_raw_tree
from thirteenf.raw_store import RawStore
from thirteenf.validation.gate_context import GateBundle


PERIODS = ("2025-12-31", "2026-03-31", "2026-06-30")


@pytest.fixture(scope="session")
def repo_root():
    return ROOT


def _cover(period: str, amendment_type=None, number=None) -> bytes:
    month_day_year = f"{period[5:7]}-{period[8:10]}-{period[:4]}"
    amended = amendment_type is not None
    detail = ""
    if amended:
        detail = (
            f"<amendmentNo>{number}</amendmentNo><amendmentInfo>"
            f"<amendmentType>{amendment_type}</amendmentType></amendmentInfo>"
        )
    form = "13F-HR/A" if amended else "13F-HR"
    return (
        f"<edgarSubmission><headerData><submissionType>{form}</submissionType>"
        f"</headerData><formData><coverPage><reportCalendarOrQuarter>"
        f"{month_day_year}</reportCalendarOrQuarter><isAmendment>"
        f"{str(amended).lower()}</isAmendment>{detail}</coverPage></formData>"
        f"</edgarSubmission>"
    ).encode()


def _positions(quarter: int, manager: int) -> list[tuple[int, int]]:
    offset = manager * 3
    if quarter == 0:
        return [(index, 100 + index + offset) for index in range(10)]
    if quarter == 1:
        values = []
        for index in range(6):
            prior = 100 + index + offset
            delta = 20 if index in (0, 3) else -20 if index in (1, 4) else 0
            values.append((index, prior + delta))
        values.extend((index, 200 + index + offset) for index in range(10, 14))
        return values
    values = [(index, 130 + index + offset) for index in range(2, 6)]
    values.extend((index, 180 + index + offset) for index in range(10, 14))
    values.extend((index, 250 + index + offset) for index in range(14, 16))
    return values


def _information_table(positions, quarter: int) -> bytes:
    rows = []
    for ordinal, (index, shares) in enumerate(positions, start=1):
        put_call = "<putCall>CALL</putCall>" if quarter == 0 and index == 9 else ""
        multiplier = 500 if quarter == 1 and index == 10 else index + 10
        rows.append(
            f"<infoTable><nameOfIssuer>ISSUER {index:02d}</nameOfIssuer>"
            f"<titleOfClass>COM</titleOfClass><cusip>{100000001 + index:09d}</cusip>"
            f"<value>{shares * multiplier}</value><shrsOrPrnAmt>"
            f"<sshPrnamt>{shares}</sshPrnamt><sshPrnamtType>SH</sshPrnamtType>"
            f"</shrsOrPrnAmt>{put_call}<investmentDiscretion>SOLE"
            f"</investmentDiscretion><otherManager></otherManager></infoTable>"
        )
    return ("<informationTable>" + "".join(rows) + "</informationTable>").encode()


def _write_filing(
    store,
    *,
    cik,
    period,
    serial,
    accepted_at,
    positions,
    quarter,
    amendment_type=None,
    amendment_number=None,
):
    accession = f"{cik:010d}-26-{serial:06d}"
    cover = store.put(_cover(period, amendment_type, amendment_number))
    info = store.put(_information_table(positions, quarter))
    form = "13F-HR/A" if amendment_type else "13F-HR"
    components = {
        "primary_document": {
            "checksum": cover.checksum,
            "object_path": cover.relative_path,
            "logical_path": f"{cik}/{accession.replace('-', '')}/primary_document.xml",
            "source_url": "https://www.sec.gov/primary_doc.xml",
            "final_url": "https://www.sec.gov/primary_doc.xml",
            "fetched_at_utc": "2026-09-05T00:00:00Z",
        },
        "information_table": {
            "checksum": info.checksum,
            "object_path": info.relative_path,
            "logical_path": f"{cik}/{accession.replace('-', '')}/info_table.xml",
            "source_url": "https://www.sec.gov/info_table.xml",
            "final_url": "https://www.sec.gov/info_table.xml",
            "fetched_at_utc": "2026-09-05T00:00:00Z",
        },
    }
    store.write_manifest(
        cik,
        accession,
        {
            "cik": cik,
            "accession": accession,
            "form_type": form,
            "filing_date": accepted_at[:10],
            "report_date": period,
            "accepted_at": accepted_at,
            "submission_source_url": f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
            "source_url": "https://www.sec.gov/info_table.xml",
            "status": "OK",
            "checksum": info.checksum,
            "fetched_at_utc": "2026-09-05T00:00:00Z",
            "components": components,
        },
    )


@pytest.fixture(scope="session")
def sample_bundle(tmp_path_factory):
    root = tmp_path_factory.mktemp("validation-bundle")
    raw_root = root / "raw"
    store = RawStore(raw_root)
    managers_path = root / "managers.csv"
    mappings_path = root / "mappings.csv"
    scoring_path = root / "scoring.yaml"
    with managers_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "label",
                "official_filer_name",
                "cik",
                "validation_status",
                "notes",
            ),
        )
        writer.writeheader()
        for manager in range(5):
            writer.writerow(
                {
                    "label": f"Manager {manager}",
                    "official_filer_name": f"MANAGER {manager}",
                    "cik": 1000001 + manager,
                    "validation_status": "VERIFIED",
                    "notes": "validation fixture",
                }
            )
    with mappings_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "cusip",
                "ticker",
                "issuer",
                "share_class",
                "mapping_status",
                "mapping_source",
                "verified_at",
                "verified_by",
                "notes",
            ),
        )
        writer.writeheader()
        for index in range(15):
            writer.writerow(
                {
                    "cusip": f"{100000001 + index:09d}",
                    "ticker": f"T{index:02d}",
                    "issuer": f"ISSUER {index:02d}",
                    "share_class": "COM",
                    "mapping_status": "VERIFIED",
                    "mapping_source": "VALIDATION_FIXTURE",
                    "verified_at": "2026-09-05",
                    "verified_by": "test",
                    "notes": "",
                }
            )
    scoring_path.write_text(
        'methodology_version: "0.1.0"\ntiers: {}\nmanagers: {}\n',
        encoding="utf-8",
    )

    for manager in range(5):
        cik = 1000001 + manager
        serial = 1
        for quarter, period in enumerate(PERIODS):
            positions = _positions(quarter, manager)
            if manager == 2 and quarter == 1:
                # One raw filing contains the same economic key twice.  The
                # independent Gate 2 implementation must sum, not overwrite.
                positions = [*positions, (0, 7)]
            accepted = (
                "2026-02-14T10:00:00Z"
                if quarter == 0
                else "2026-05-14T10:00:00Z"
                if quarter == 1
                else "2026-08-14T10:00:00Z"
            )
            _write_filing(
                store,
                cik=cik,
                period=period,
                serial=serial,
                accepted_at=accepted,
                positions=positions,
                quarter=quarter,
            )
            serial += 1
            if manager == 1 and quarter == 1:
                _write_filing(
                    store,
                    cik=cik,
                    period=period,
                    serial=serial,
                    accepted_at="2026-05-15T10:00:00Z",
                    positions=[(16, 40), (17, 41)],
                    quarter=quarter,
                    amendment_type="NEW HOLDINGS",
                    amendment_number=1,
                )
                serial += 1
            if manager == 0 and quarter == 2:
                amended = [(index, shares + 1) for index, shares in positions]
                _write_filing(
                    store,
                    cik=cik,
                    period=period,
                    serial=serial,
                    accepted_at="2026-08-15T10:00:00Z",
                    positions=amended,
                    quarter=quarter,
                    amendment_type="RESTATEMENT",
                    amendment_number=1,
                )
                serial += 1

    db_path = root / "bundle.db"
    summary = normalize_raw_tree(
        raw_root,
        db_path,
        managers_path=managers_path,
        mappings_path=mappings_path,
        scoring_path=scoring_path,
        methodology_version="0.1.0",
    )
    assert summary.promoted, summary.errors
    return GateBundle(
        raw_root=raw_root,
        db_path=db_path,
        methodology_version="0.1.0",
    )
