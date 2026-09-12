from __future__ import annotations

import hashlib
import shutil
import sqlite3
import pytest

from thirteenf.validation.gate1 import run_gate1
from thirteenf.validation.gate_context import GateBundle, build_gate_context
from thirteenf.raw_store import RawStore


def test_gate1_rejects_lowered_acceptance_threshold(sample_bundle):
    with pytest.raises(ValueError, match='5.*3.*10'):
        run_gate1(sample_bundle, managers=0, quarters=0, rows_per_filing=0)


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


def test_context_rejects_missing_raw_without_creating_it(sample_bundle, tmp_path):
    missing = tmp_path / "missing-raw"
    with pytest.raises(RuntimeError, match="raw"):
        build_gate_context(GateBundle(missing, sample_bundle.db_path, "0.1.0"))
    assert not missing.exists()


def test_context_rejects_live_database_sidecar(sample_bundle, tmp_path):
    db = tmp_path / "snapshot.db"
    shutil.copy2(sample_bundle.db_path, db)
    db.with_name(db.name + "-wal").write_bytes(b"not checkpointed")
    with pytest.raises(RuntimeError, match="sidecar"):
        build_gate_context(GateBundle(sample_bundle.raw_root, db, "0.1.0"))


def _source_snapshot(root):
    import json
    store = RawStore(root)
    source = store.put(b'{"filings": {"recent": {}}}')
    record = {'cik': 1, 'accession_number': '0000000001-26-000001',
              'submission_source_url': 'https://data.sec.gov/submissions/CIK0000000001.json',
              'submission_source_checksum': source.checksum}
    manifest = {**record, 'accession': record['accession_number'], 'status': 'OK', 'components': {}}
    store.write_manifest(1, manifest['accession'], manifest)
    inventory = {'schema_version': 2, 'cik': 1, 'as_of': '2026-09-07', 'quarters': 12,
                 'status': 'COMPLETE', 'completed_at_utc': '2026-09-07T00:00:00Z',
                 'sources': [{'cik': 1, 'source_url': record['submission_source_url'],
                              'checksum': source.checksum, 'object_path': source.relative_path,
                              'fetched_at_utc': '2026-09-07T00:00:00Z'}],
                 'skipped_shards': [], 'eligible_accessions': [record]}
    path = store.write_discovery_inventory(1, inventory)
    return store, source, inventory, path


def test_raw_fingerprint_binds_discovery_scope_but_not_transport_times(tmp_path):
    import json
    from thirteenf.validation.gate_context import _tree_hash
    _, _, inventory, path = _source_snapshot(tmp_path)
    before = _tree_hash(tmp_path)
    inventory['completed_at_utc'] = '2026-09-07T01:00:00Z'
    inventory['sources'][0]['fetched_at_utc'] = '2026-09-07T01:00:00Z'
    path.write_text(json.dumps(inventory), encoding='utf-8')
    assert _tree_hash(tmp_path) == before
    inventory['as_of'] = '2026-09-08'
    path.write_text(json.dumps(inventory), encoding='utf-8')
    assert _tree_hash(tmp_path) != before


def test_raw_fingerprint_rejects_corrupted_discovery_source(tmp_path):
    from thirteenf.validation.gate_context import _tree_hash
    _, source, _, _ = _source_snapshot(tmp_path)
    (tmp_path / source.relative_path).write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='checksum'):
        _tree_hash(tmp_path)


@pytest.mark.parametrize('mutation', ['incomplete', 'missing_accession', 'old_schema', 'wrong_cik'])
def test_raw_fingerprint_rejects_unverified_discovery_inventory(tmp_path, mutation):
    import json
    from thirteenf.validation.gate_context import _tree_hash
    _, _, inventory, path = _source_snapshot(tmp_path)
    if mutation == 'incomplete': inventory['status'] = 'INCOMPLETE'
    elif mutation == 'missing_accession': inventory['eligible_accessions'] = []
    elif mutation == 'old_schema': inventory.pop('schema_version')
    else: inventory['sources'][0]['cik'] = 2
    path.write_text(json.dumps(inventory), encoding='utf-8')
    with pytest.raises(RuntimeError, match='discovery'):
        _tree_hash(tmp_path)
