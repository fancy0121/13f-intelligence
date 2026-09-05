from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.normalization import normalize_raw_tree
from thirteenf.raw_store import RawStore


INFO_XML = b"""<?xml version="1.0"?>
<informationTable>
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip><value>1000</value>
    <shrsOrPrnAmt><sshPrnamt>100</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
</informationTable>"""


def _cover(amendment_type=None, number=None):
    is_amendment = amendment_type is not None
    amendment = ""
    if is_amendment:
        amendment = (
            f"<amendmentNo>{number}</amendmentNo><amendmentInfo>"
            f"<amendmentType>{amendment_type}</amendmentType></amendmentInfo>"
        )
    form = "13F-HR/A" if is_amendment else "13F-HR"
    return f"""<?xml version="1.0"?>
    <edgarSubmission><headerData><submissionType>{form}</submissionType></headerData>
    <formData><coverPage><reportCalendarOrQuarter>06-30-2026</reportCalendarOrQuarter>
    <isAmendment>{str(is_amendment).lower()}</isAmendment>{amendment}
    </coverPage></formData></edgarSubmission>""".encode()


def _configs(tmp_path):
    managers = tmp_path / "managers.csv"
    managers.write_text(
        "label,official_filer_name,cik,validation_status,notes\n"
        "Test Manager,TEST MANAGER,1,VERIFIED,test\n",
        encoding="utf-8",
    )
    mappings = tmp_path / "mappings.csv"
    mappings.write_text(
        "cusip,ticker,issuer,share_class,mapping_status,mapping_source,verified_at,verified_by,notes\n"
        "037833100,AAPL,Apple Inc.,COM,VERIFIED,MANUAL_REVIEW,2026-09-05,test,test\n",
        encoding="utf-8",
    )
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text(
        'methodology_version: "0.1.0"\ntiers: {}\nmanagers: {}\n',
        encoding="utf-8",
    )
    return managers, mappings, scoring


def _manifest(
    raw_root,
    *,
    accession="0000000001-26-000001",
    accepted_at="2026-08-14T10:00:00Z",
    amendment_type=None,
    amendment_number=None,
    status="OK",
    include_primary=True,
    corrupt_info_checksum=False,
):
    store = RawStore(raw_root)
    primary = store.put(_cover(amendment_type, amendment_number))
    info = store.put(INFO_XML)
    components = {
        "information_table": {
            "checksum": "0" * 64 if corrupt_info_checksum else info.checksum,
            "object_path": info.relative_path,
            "logical_path": f"1/{accession.replace('-', '')}/info_table.xml",
            "source_url": "https://www.sec.gov/info.xml",
            "final_url": "https://www.sec.gov/info.xml",
            "fetched_at_utc": "2026-09-05T00:00:00Z",
        }
    }
    if include_primary:
        components["primary_document"] = {
            "checksum": primary.checksum,
            "object_path": primary.relative_path,
            "logical_path": f"1/{accession.replace('-', '')}/primary_document.xml",
            "source_url": "https://www.sec.gov/primary_doc.xml",
            "final_url": "https://www.sec.gov/primary_doc.xml",
            "fetched_at_utc": "2026-09-05T00:00:00Z",
        }
    store.write_manifest(
        1,
        accession,
        {
            "cik": 1,
            "accession": accession,
            "form_type": "13F-HR/A" if amendment_type else "13F-HR",
            "filing_date": accepted_at[:10],
            "report_date": "2026-06-30",
            "accepted_at": accepted_at,
            "submission_source_url": "https://data.sec.gov/submissions/CIK0000000001.json",
            "source_url": "https://www.sec.gov/info.xml",
            "status": status,
            "checksum": info.checksum,
            "fetched_at_utc": "2026-09-05T00:00:00Z",
            "components": components,
        },
    )


def _normalize(tmp_path, raw_root, db_path):
    managers, mappings, scoring = _configs(tmp_path)
    return normalize_raw_tree(
        raw_root,
        db_path,
        managers_path=managers,
        mappings_path=mappings,
        scoring_path=scoring,
        methodology_version="0.1.0",
    )


def test_valid_raw_tree_builds_and_promotes_complete_database(tmp_path):
    raw_root = tmp_path / "raw"
    db_path = tmp_path / "release.db"
    _manifest(raw_root)
    summary = _normalize(tmp_path, raw_root, db_path)
    assert summary.processed == 1
    assert summary.failed == 0
    assert summary.pending_amendments == 0
    assert summary.promoted is True

    conn = sqlite3.connect(db_path)
    holding = conn.execute(
        """
        SELECT ssh_prnamt_type, investment_discretion, shares, value
        FROM holdings
        """
    ).fetchone()
    assert tuple(holding) == ("SH", "SOLE", 100, 1000)
    assert conn.execute(
        "SELECT status FROM effective_periods"
    ).fetchone()[0] == "READY"
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


def test_unknown_manifest_status_fails_without_replacing_database(tmp_path):
    raw_root = tmp_path / "raw"
    db_path = tmp_path / "release.db"
    db_path.write_bytes(b"existing-release")
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    _manifest(raw_root, status="MYSTERY")
    summary = _normalize(tmp_path, raw_root, db_path)
    assert summary.failed == 1
    assert summary.skipped == 0
    assert summary.promoted is False
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before


def test_missing_primary_document_blocks_promotion(tmp_path):
    raw_root = tmp_path / "raw"
    _manifest(raw_root, include_primary=False)
    summary = _normalize(tmp_path, raw_root, tmp_path / "release.db")
    assert summary.failed == 1
    assert summary.promoted is False


def test_checksum_mismatch_blocks_promotion(tmp_path):
    raw_root = tmp_path / "raw"
    _manifest(raw_root, corrupt_info_checksum=True)
    summary = _normalize(tmp_path, raw_root, tmp_path / "release.db")
    assert summary.failed == 1
    assert any("checksum" in error.lower() for error in summary.errors)


def test_unknown_amendment_type_is_pending_and_blocks_promotion(tmp_path):
    raw_root = tmp_path / "raw"
    _manifest(raw_root, amendment_type="UNKNOWN", amendment_number=1)
    summary = _normalize(tmp_path, raw_root, tmp_path / "release.db")
    assert summary.pending_amendments == 1
    assert summary.promoted is False


def test_amendments_link_to_immediate_predecessor(tmp_path):
    raw_root = tmp_path / "raw"
    db_path = tmp_path / "release.db"
    _manifest(raw_root)
    _manifest(
        raw_root,
        accession="0000000001-26-000002",
        accepted_at="2026-08-15T10:00:00Z",
        amendment_type="NEW HOLDINGS",
        amendment_number=1,
    )
    _manifest(
        raw_root,
        accession="0000000001-26-000003",
        accepted_at="2026-08-16T10:00:00Z",
        amendment_type="RESTATEMENT",
        amendment_number=2,
    )
    summary = _normalize(tmp_path, raw_root, db_path)
    assert summary.promoted is True

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT filing_id, accession_number, amends_filing_id
        FROM filings ORDER BY accepted_at
        """
    ).fetchall()
    assert rows[1][2] == rows[0][0]
    assert rows[2][2] == rows[1][0]
    conn.close()
