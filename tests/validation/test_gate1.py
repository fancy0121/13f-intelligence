from __future__ import annotations

import hashlib
import shutil
import sqlite3

from thirteenf.validation.gate1 import run_gate1
from thirteenf.validation.gate_context import GateBundle
from thirteenf.raw_store import RawStore


def test_gate1_is_independent_and_checks_required_sample(monkeypatch, sample_bundle):
    monkeypatch.setattr(
        "thirteenf.parser.parse_info_table",
        lambda _: (_ for _ in ()).throw(AssertionError("production parser called")),
    )
    before = hashlib.sha256(sample_bundle.db_path.read_bytes()).hexdigest()
    result = run_gate1(
        sample_bundle,
        managers=5,
        quarters=3,
        rows_per_filing=10,
    )
    after = hashlib.sha256(sample_bundle.db_path.read_bytes()).hexdigest()
    assert result.passed
    assert result.checked_rows == 150
    assert len(result.manager_ids) == 5
    assert result.mismatches == ()
    assert before == after


def test_gate1_detects_corrupted_normalized_field(sample_bundle, tmp_path):
    copied = tmp_path / "corrupt.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute("UPDATE holdings SET shares=shares+1 WHERE holding_id=(SELECT MIN(holding_id) FROM holdings)")
    conn.commit()
    conn.close()
    result = run_gate1(
        GateBundle(sample_bundle.raw_root, copied, "0.1.0"),
        managers=5,
        quarters=3,
        rows_per_filing=10,
    )
    assert not result.passed
    assert result.mismatches


def test_gate1_detects_corrupted_preserved_object(sample_bundle, tmp_path):
    copied_raw = tmp_path / "raw"
    shutil.copytree(sample_bundle.raw_root, copied_raw)
    conn = sqlite3.connect(sample_bundle.db_path)
    cik, accession = conn.execute(
        """
        SELECT m.cik, f.accession_number
        FROM holdings h
        JOIN filings f ON f.filing_id=h.filing_id
        JOIN managers m ON m.manager_id=f.manager_id
        WHERE h.holding_id=(SELECT MIN(holding_id) FROM holdings)
        """
    ).fetchone()
    conn.close()
    manifest = RawStore(copied_raw).load_manifest(cik, accession)
    object_path = manifest["components"]["information_table"]["object_path"]
    path = copied_raw / object_path
    path.write_bytes(path.read_bytes() + b"\n")
    result = run_gate1(
        GateBundle(copied_raw, sample_bundle.db_path, "0.1.0"),
        managers=5,
        quarters=3,
        rows_per_filing=10,
    )
    assert not result.passed
    assert any(item["kind"] == "raw_document" for item in result.mismatches)
