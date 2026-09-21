"""Golden fixtures: real SEC filing samples verifying parser fidelity.

Fixture source: Trian Fund Management L.P. 13F-HR for 2025-06-30
(accession 0001345471-25-000028, information table Q22025-tfmlp-info-table.xml,
downloaded from SEC EDGAR on 2026-08-24). The expected rows below were read
directly from that SEC original file.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.parser import AmendmentType, parse_cover_page, parse_info_table


def test_golden_real_sec_filing_parses_exactly():
    fixture = ROOT / "tests" / "fixtures" / "trian_Q22025_info_table.xml"
    rows = parse_info_table(fixture.read_bytes())
    assert len(rows) == 11

    first = rows[0]
    assert first.row_ordinal == 1
    assert first.name_of_issuer == "Ferguson Plc New"
    assert first.title_of_class == "SHS"
    assert first.cusip == "G3421J106"
    assert first.value == 236554237
    assert first.shares == 1086357.0
    assert first.put_call == ""

    second = rows[1]
    assert second.name_of_issuer == "GE Aerospace"
    assert second.cusip == "369604301"
    assert second.value == 1037336524
    assert second.shares == 4030213.0

    fifth = rows[4]
    assert fifth.name_of_issuer == "Janus Henderson Group plc"
    assert fifth.cusip == "G4474Y214"
    assert fifth.value == 1237745352
    assert fifth.shares == 31867800.0


def test_golden_fixture_no_put_call_rows():
    fixture = ROOT / "tests" / "fixtures" / "trian_Q22025_info_table.xml"
    rows = parse_info_table(fixture.read_bytes())
    assert all(r.put_call == "" for r in rows)


def test_cover_add_new_holdings_real_sec_extract():
    fixture = ROOT / "tests" / "fixtures" / "sec_add_holdings_primary_doc.xml"
    cover = parse_cover_page(fixture.read_bytes())
    assert cover.report_period == "2026-03-31"
    assert cover.amendment_number == 1
    assert cover.amendment_type is AmendmentType.ADD_NEW_HOLDINGS


def test_cover_restatement_real_sec_extract():
    fixture = ROOT / "tests" / "fixtures" / "sec_restatement_primary_doc.xml"
    cover = parse_cover_page(fixture.read_bytes())
    assert cover.report_period == "2026-03-31"
    assert cover.amendment_number == 1
    assert cover.amendment_type is AmendmentType.RESTATEMENT


def test_cover_extract_payload_hashes_are_stable():
    expected = {
        "sec_add_holdings_primary_doc.xml": "24b0d9ea7240e6627289a7a731536de4da21a98b377b5f8700b69091a2bdd127",
        "sec_restatement_primary_doc.xml": "58918534d1b22f84d8f97a675b32f56f6bfb1a714c6b760c04354a8262457a98",
    }
    for name, checksum in expected.items():
        content = (ROOT / "tests" / "fixtures" / name).read_bytes()
        payload = content[content.index(b"<edgarSubmission") :].replace(b"\r\n", b"\n")
        assert hashlib.sha256(payload).hexdigest() == checksum
