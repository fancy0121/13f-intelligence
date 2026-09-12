"""Synthetic attestations test enforcement, never real release approval."""
import hashlib
import json
from dataclasses import asdict

import pytest

from thirteenf.validation.gate_context import (
    build_gate_context, verify_public_snapshot,
)


def _attestation(bundle, tmp_path):
    context = asdict(build_gate_context(bundle))
    files = {}
    hashes = {}
    for name in ("resolution", "semantic", "managers"):
        path = tmp_path / (name + ".csv")
        path.write_text("synthetic test only", encoding="utf-8")
        files[name] = path
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "schema_version": 1, "releaseable": True, "context": context,
        "gate3": "PENDING_REAL_WORLD_VALIDATION", "files": hashes,
        "gate1": {"status": "PASS", "checked_rows": 150, "manager_ids": [1,2,3,4,5], "mismatches": [], "context": context},
        "gate2": {"automatic_status": "PASS", "human_status": "PASS", "releaseable": True, "checked_transitions": 30, "manager_ids": [1,2,3,4,5], "mismatches": [], "manual_errors": [], "context": context},
    }
    path = tmp_path / "release-manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload, files


def test_public_snapshot_requires_attestation_even_with_valid_v3_database(sample_bundle, tmp_path):
    with pytest.raises(RuntimeError, match="manifest"):
        verify_public_snapshot(sample_bundle.db_path, tmp_path / "missing.json", {})


def test_synthetic_attestation_integrity_and_no_database_writes(sample_bundle, tmp_path):
    path, _, files = _attestation(sample_bundle, tmp_path)
    before = sample_bundle.db_path.read_bytes()
    verify_public_snapshot(sample_bundle.db_path, path, files)
    assert sample_bundle.db_path.read_bytes() == before


@pytest.mark.parametrize("problem", ["human", "database", "runtime", "sidecar", "context", "gate3"])
def test_public_snapshot_rejects_incomplete_or_different_evidence(sample_bundle, tmp_path, problem):
    path, payload, files = _attestation(sample_bundle, tmp_path)
    if problem == "human":
        payload["gate2"]["human_status"] = "NOT_REVIEWED"
    elif problem in {"database", "runtime"}:
        field = "db_sha256" if problem == "database" else "runtime_hash"
        payload["context"][field] = "0" * 64
    elif problem == "sidecar":
        files["resolution"].write_text("changed", encoding="utf-8")
    elif problem == "context":
        payload["gate1"]["context"] = {}
    else:
        payload["gate3"] = "PASS"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError):
        verify_public_snapshot(sample_bundle.db_path, path, files)
