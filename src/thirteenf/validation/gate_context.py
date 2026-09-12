"""Immutable bundle identity and read-only gate context fingerprints."""

from __future__ import annotations

import hashlib
import argparse
import json
import platform
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from thirteenf.database import connect_readonly
from thirteenf.raw_store import RawStore


@dataclass(frozen=True)
class GateBundle:
    raw_root: Path
    db_path: Path
    methodology_version: str
    quarantine_policy_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_root", Path(self.raw_root).resolve())
        object.__setattr__(self, "db_path", Path(self.db_path).resolve())
        if self.quarantine_policy_path is not None:
            object.__setattr__(self, "quarantine_policy_path", Path(self.quarantine_policy_path).resolve())


@dataclass(frozen=True)
class GateContext:
    raw_fingerprint: str
    effective_fingerprint: str
    db_sha256: str
    runtime_hash: str
    methodology_version: str
    gate_hash: str


def build_gate_context(bundle: GateBundle) -> GateContext:
    if not bundle.raw_root.is_dir() or not (bundle.raw_root / "manifests").is_dir():
        raise RuntimeError("canonical raw manifests are missing")
    if not bundle.db_path.is_file():
        raise RuntimeError("database snapshot is missing")
    for suffix in ("-wal", "-shm"):
        if Path(str(bundle.db_path) + suffix).exists():
            raise RuntimeError("database snapshot has a live sidecar")
    raw = _tree_hash(bundle.raw_root)
    database_hash = _sha256(bundle.db_path.read_bytes())
    conn = connect_readonly(bundle.db_path, immutable=True)
    try:
        if [r[0] for r in conn.execute("PRAGMA integrity_check")] != ["ok"]:
            raise RuntimeError("database integrity check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("database foreign key check failed")
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
    runtime = runtime_hash()
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


def runtime_hash() -> str:
    return _sha256(
        json.dumps(
            {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "validator": "13f-independent-gates-v1",
                "source_hash": runtime_source_hash(),
            },
            sort_keys=True,
        ).encode()
    )


def verify_public_snapshot(db_path: Path, manifest_path: Path, files: dict[str, Path]) -> None:
    """Verify trusted release attestation against bytes served by the UI.

    This does not manufacture approval or replace the independent raw Gates.
    The manifest must be supplied by a trusted release publisher, never users.
    """
    if not manifest_path.is_file():
        raise RuntimeError("release manifest missing")
    if any(Path(str(db_path) + suffix).exists() for suffix in ("-wal", "-shm")):
        raise RuntimeError("public snapshot has a live database sidecar")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("releaseable") is not True:
        raise RuntimeError("release not approved")
    if payload.get("gate3") != "PENDING_REAL_WORLD_VALIDATION":
        raise RuntimeError("Gate 3 real-world validation has not been established")
    context = payload.get("context", {})
    fields = ("raw_fingerprint", "effective_fingerprint", "db_sha256", "runtime_hash", "gate_hash")
    if not all(re.fullmatch(r"[0-9a-f]{64}", str(context.get(k, ""))) for k in fields):
        raise RuntimeError("invalid release context")
    method = context.get("methodology_version")
    if not isinstance(method, str) or not method:
        raise RuntimeError("missing methodology identity")
    expected = _sha256(":".join(str(context[k]) for k in (
        "raw_fingerprint", "effective_fingerprint", "db_sha256", "runtime_hash", "methodology_version"
    )).encode())
    if expected != context["gate_hash"]:
        raise RuntimeError("release context fingerprint mismatch")
    gate1, gate2 = payload.get("gate1", {}), payload.get("gate2", {})
    if (gate1.get("status") != "PASS" or gate1.get("mismatches") != []
            or gate1.get("checked_rows", 0) < 150 or len(set(gate1.get("manager_ids", []))) < 5):
        raise RuntimeError("Gate 1 not approved")
    if (gate2.get("automatic_status") != "PASS" or gate2.get("human_status") != "PASS"
            or gate2.get("releaseable") is not True or gate2.get("mismatches") != []
            or gate2.get("manual_errors") != [] or gate2.get("checked_transitions", 0) < 30
            or len(set(gate2.get("manager_ids", []))) < 5):
        raise RuntimeError("Gate 2 not approved")
    if gate1.get("context") != context or gate2.get("context") != context:
        raise RuntimeError("Gates refer to different snapshots")
    if _sha256(db_path.read_bytes()) != context["db_sha256"]:
        raise RuntimeError("public database checksum mismatch")
    if runtime_hash() != context["runtime_hash"]:
        raise RuntimeError("public runtime checksum mismatch")
    if set(files) != {"resolution", "semantic", "managers"}:
        raise RuntimeError("public metadata file identities missing")
    for key, path in files.items():
        if _sha256(path.read_bytes()) != payload.get("files", {}).get(key):
            raise RuntimeError("public metadata checksum mismatch")
    conn = connect_readonly(db_path, immutable=True)
    try:
        versions = [r[0] for r in conn.execute("SELECT DISTINCT methodology_version FROM effective_periods")]
        if versions != [method] or conn.execute("SELECT 1 FROM effective_periods WHERE status!='READY' LIMIT 1").fetchone():
            raise RuntimeError("public effective state is not READY")
    finally:
        conn.close()


def manifest_for(bundle: GateBundle, cik: int, accession: str) -> dict:
    if not bundle.raw_root.is_dir():
        raise RuntimeError("raw root is missing")
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
    # Transport timestamps and unreferenced historical objects do not change
    # the identity of the current source snapshot.
    entries = []
    store = RawStore(root)
    manifests = []
    for path in sorted((root / "manifests").rglob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifests.append(manifest)
        identity = {k: manifest.get(k) for k in (
            "cik", "accession", "form_type", "filing_date", "report_date",
            "accepted_at", "submission_source_url", "submission_source_checksum", "source_url", "status",
        )}
        components = {}
        for name, component in sorted((manifest.get("components") or {}).items()):
            relative = component.get("object_path", "")
            candidate = store._path(Path(relative))
            components[name] = {
                "checksum": component.get("checksum"),
                "source_url": component.get("source_url"),
                "actual_checksum": _sha256(candidate.read_bytes()),
            }
        identity["components"] = components
        entries.append((path.relative_to(root).as_posix(), identity))
    if not entries:
        raise RuntimeError("canonical raw manifest set is empty")
    entries.extend(_discovery_identity(root, store, manifests))
    return _sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode())


def _discovery_identity(root: Path, store: RawStore, manifests: list[dict]) -> list:
    """Bind the latest strict discovery scope and its raw source bytes.

    Historical fixture bundles without discovery are supported. Once a bundle
    carries discovery evidence, incomplete inventories cannot fall back to them.
    """
    latest = {}
    for path in sorted((root / "discovery_runs").glob("*/*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        cik = int(item["cik"])
        if path.parent.name != f"{cik:010d}":
            raise RuntimeError("discovery CIK path mismatch")
        if cik not in latest or item["completed_at_utc"] > latest[cik]["completed_at_utc"]:
            latest[cik] = item
    if not latest and not any(m.get("submission_source_checksum") for m in manifests):
        return []
    grouped = {}
    for manifest in manifests:
        grouped.setdefault(int(manifest["cik"]), []).append(manifest)
    if set(grouped) != set(latest):
        raise RuntimeError("discovery manager coverage mismatch")
    result = []
    fields = {"accession_number": "accession", "form_type": "form_type", "filing_date": "filing_date",
              "report_date": "report_date", "accepted_at": "accepted_at",
              "submission_source_url": "submission_source_url",
              "submission_source_checksum": "submission_source_checksum"}
    for cik, inventory in sorted(latest.items()):
        if inventory.get("schema_version") != 2 or inventory.get("status") != "COMPLETE":
            raise RuntimeError(f"discovery inventory not strictly validated for CIK {cik}")
        eligible = inventory["eligible_accessions"]
        by_accession = {r["accession_number"]: r for r in eligible}
        if (len(by_accession) != len(eligible)
                or set(by_accession) != {m["accession"] for m in grouped[cik]}):
            raise RuntimeError(f"discovery accession coverage mismatch for CIK {cik}")
        sources = []
        source_keys = set()
        for source in inventory["sources"]:
            if int(source["cik"]) != cik:
                raise RuntimeError("discovery source CIK mismatch")
            store.read_object(source["object_path"], source["checksum"])
            source_keys.add((source["source_url"], source["checksum"]))
            sources.append({k: source.get(k) for k in ("cik", "source_url", "final_url", "checksum")})
        for manifest in grouped[cik]:
            record = by_accession[manifest["accession"]]
            if int(record["cik"]) != cik or any(record.get(a) != manifest.get(b) for a, b in fields.items()):
                raise RuntimeError("discovery accession metadata mismatch")
            key = (manifest.get("submission_source_url"), manifest.get("submission_source_checksum"))
            if key not in source_keys:
                raise RuntimeError("discovery source identity missing")
        identity = {k: inventory[k] for k in ("schema_version", "cik", "as_of", "quarters", "status")}
        identity.update(
            sources=sorted(sources, key=lambda s: (s["source_url"], s["checksum"])),
            skipped_shards=sorted(inventory["skipped_shards"], key=lambda s: s["name"]),
            eligible_accessions=sorted(eligible, key=lambda r: r["accession_number"]),
        )
        result.append((f"discovery_runs/{cik:010d}", identity))
    return result


def runtime_source_hash(root: Path | None = None) -> str:
    root = root or Path(__file__).resolve().parents[3]
    patterns = (
        "src/**/*.py", "app/**/*.py", "scripts/*.py", "config/managers.csv",
        "config/manager_scoring.yaml", "config/methodology.yaml",
        "config/source_quarantine.json",
        "config/ticker_mappings.csv", "config/historical_symbols.csv",
        "reports/research/security_resolution_master.csv",
        "reports/research/security_semantic_classification.csv",
        "requirements*.txt", "requirements*.lock", "pyproject.toml", "Dockerfile",
        ".streamlit/config.toml", "config/display_names.csv",
    )
    paths = {p for pattern in patterns for p in root.glob(pattern) if p.is_file()}
    return _sha256(json.dumps([
        (p.relative_to(root).as_posix(), _sha256(p.read_bytes())) for p in sorted(paths)
    ], separators=(",", ":")).encode())


def _query_hash(conn: sqlite3.Connection, query: str) -> str:
    rows = [tuple(row) for row in conn.execute(query).fetchall()]
    return _sha256(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()
    )


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--methodology-version", default="0.1.0")
    args = parser.parse_args(argv)
    try:
        context = build_gate_context(GateBundle(args.raw_root, args.db, args.methodology_version))
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(json.dumps({"status": "NOT_VALIDATED", "error": str(exc)}))
        return 1
    print(json.dumps(asdict(context), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
