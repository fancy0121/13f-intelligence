"""Immutable bundle identity and read-only gate context fingerprints."""

from __future__ import annotations

import hashlib
import json
import platform
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from thirteenf.database import connect_readonly
from thirteenf.raw_store import RawStore


@dataclass(frozen=True)
class GateBundle:
    raw_root: Path
    db_path: Path
    methodology_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_root", Path(self.raw_root).resolve())
        object.__setattr__(self, "db_path", Path(self.db_path).resolve())


@dataclass(frozen=True)
class GateContext:
    raw_fingerprint: str
    effective_fingerprint: str
    db_sha256: str
    runtime_hash: str
    methodology_version: str
    gate_hash: str


def build_gate_context(bundle: GateBundle) -> GateContext:
    raw = _tree_hash(bundle.raw_root)
    database_hash = _sha256(bundle.db_path.read_bytes())
    conn = connect_readonly(bundle.db_path, immutable=True)
    try:
        effective = _query_hash(
            conn,
            """
            SELECT manager_id, report_period, methodology_version, state_hash,
                   status, total_value
            FROM effective_periods ORDER BY manager_id, report_period,
                 methodology_version
            """,
        )
    finally:
        conn.close()
    runtime = _sha256(
        json.dumps(
            {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "validator": "13f-independent-gates-v1",
            },
            sort_keys=True,
        ).encode()
    )
    gate_hash = _sha256(
        f"{raw}:{effective}:{database_hash}:{runtime}:{bundle.methodology_version}".encode()
    )
    return GateContext(
        raw_fingerprint=raw,
        effective_fingerprint=effective,
        db_sha256=database_hash,
        runtime_hash=runtime,
        methodology_version=bundle.methodology_version,
        gate_hash=gate_hash,
    )


def manifest_for(bundle: GateBundle, cik: int, accession: str) -> dict:
    store = RawStore(bundle.raw_root)
    manifest = store.load_manifest(cik, accession)
    if not manifest:
        raise RuntimeError(f"manifest missing for {accession}")
    return manifest


def component_bytes(
    bundle: GateBundle,
    cik: int,
    accession: str,
    component: str,
) -> bytes:
    manifest = manifest_for(bundle, cik, accession)
    value = (manifest.get("components") or {}).get(component)
    if not isinstance(value, dict):
        raise RuntimeError(f"{accession}: missing {component}")
    checksum = str(value.get("checksum") or "")
    object_path = str(value.get("object_path") or "")
    return RawStore(bundle.raw_root).read_object(object_path, checksum)


def _tree_hash(root: Path) -> str:
    entries = []
    for subdir in ("manifests", "objects"):
        base = root / subdir
        if not base.exists():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            entries.append(
                (
                    path.relative_to(root).as_posix(),
                    _sha256(path.read_bytes()),
                )
            )
    return _sha256(json.dumps(entries, separators=(",", ":")).encode())


def _query_hash(conn: sqlite3.Connection, query: str) -> str:
    rows = [tuple(row) for row in conn.execute(query).fetchall()]
    return _sha256(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()
    )


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
