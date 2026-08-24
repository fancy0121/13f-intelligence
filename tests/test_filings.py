from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.filings import (
    FilingRecord,
    dedupe_effective,
    latest_n_quarters,
    parse_submissions,
)


def _record(report_date: str, accession: str, form: str = "13F-HR") -> FilingRecord:
    return FilingRecord(
        cik=1,
        accession_number=accession,
        form_type=form,
        filing_date="2026-08-14",
        report_date=report_date,
        primary_document="InfoTable.xml",
    )


def test_parse_submissions_filters_13f_only():
    payload = {
        "filings": {
            "recent": {
                "form": ["13F-HR", "4", "13F-HR/A", "SC 13G"],
                "accessionNumber": ["1", "2", "3", "4"],
                "filingDate": ["2026-08-14"] * 4,
                "reportDate": ["2026-06-30", "", "2026-06-30", ""],
                "primaryDocument": ["InfoTable.xml", "", "InfoTable.xml", ""],
            }
        }
    }
    records = parse_submissions(7, payload)
    assert [r.form_type for r in records] == ["13F-HR", "13F-HR/A"]
    assert records[1].is_amendment


def test_latest_n_quarters_window():
    records = [
        _record("2026-06-30", "a"),
        _record("2026-03-31", "b"),
        _record("2025-12-31", "c"),
        _record("2025-09-30", "d"),
        _record("2025-06-30", "e"),
        _record("2025-03-31", "f"),
        _record("2024-12-31", "g"),
        _record("2024-09-30", "h"),
        _record("2024-06-30", "i"),
        _record("2024-03-31", "j"),
        _record("2023-12-31", "k"),
        _record("2023-09-30", "l"),
        _record("2023-06-30", "m"),
    ]
    kept = latest_n_quarters(records, n=12)
    assert len(kept) == 12
    assert kept[-1].report_date == "2023-09-30"


def test_dedupe_effective_prefers_amendment():
    base = _record("2026-06-30", "A1")
    amend = FilingRecord(
        cik=1,
        accession_number="A2",
        form_type="13F-HR/A",
        filing_date="2026-08-20",
        report_date="2026-06-30",
        primary_document="InfoTable.xml",
    )
    chosen = dedupe_effective([base, amend])
    assert len(chosen) == 1
    assert chosen[0].accession_number == "A2"


def test_dedupe_effective_keeps_both_periods():
    records = [_record("2026-06-30", "A1"), _record("2026-03-31", "B1")]
    chosen = dedupe_effective(records)
    assert len(chosen) == 2

