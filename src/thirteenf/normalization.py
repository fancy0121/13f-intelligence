"""Fail-closed, atomic rebuild from preserved SEC raw components."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath

from thirteenf.changes import compute_portfolio_weights, compute_position_changes
from thirteenf.consensus import compute_consensus
from thirteenf.database import (
    add_quality_event,
    backfill_holding_tickers,
    bulk_ensure_securities,
    connect,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)
from thirteenf.manager_scoring import apply_scoring
from thirteenf.parser import (
    CoverMetadata,
    HoldingRow,
    XmlParseError,
    parse_cover_page,
    parse_info_table,
)
from thirteenf.quality import run_all as run_quality_checks
from thirteenf.raw_store import RawStore
from thirteenf.security_master import load_mappings, resolve
from thirteenf.trends import compute_trends


ROOT = Path(__file__).resolve().parents[2]
KNOWN_MANIFEST_STATUSES = frozenset(
    {"OK", "NO_INFO_TABLE", "NO_PRIMARY_DOCUMENT", "FAILED"}
)


@dataclass(frozen=True)
class NormalizationSummary:
    processed: int
    failed: int
    pending_amendments: int
    skipped: int
    promoted: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _NormalizedFiling:
    manifest: dict
    cover: CoverMetadata
    rows: tuple[HoldingRow, ...]
    info_checksum: str
    info_path: str
    cover_checksum: str
    cover_path: str
    fetched_at_utc: str
    source_url: str


def normalize_raw_tree(
    raw_root: Path | str,
    db_path: Path | str,
    *,
    managers_path: Path | str = ROOT / "config" / "managers.csv",
    mappings_path: Path | str = ROOT / "config" / "ticker_mappings.csv",
    scoring_path: Path | str = ROOT / "config" / "manager_scoring.yaml",
    methodology_version: str = "0.1.0",
) -> NormalizationSummary:
    """Validate all raw evidence, build a staging DB, then atomically promote."""

    raw_root = Path(raw_root).resolve()
    db_path = Path(db_path).resolve()
    managers_path = Path(managers_path)
    mappings_path = Path(mappings_path)
    scoring_path = Path(scoring_path)
    verified = _load_verified_managers(managers_path)
    if not verified:
        return NormalizationSummary(
            processed=0,
            failed=1,
            pending_amendments=0,
            skipped=0,
            promoted=False,
            errors=("manager configuration has no verified CIKs",),
        )
    store = RawStore(raw_root)
    manifest_paths = sorted((raw_root / "manifests").glob("*/*.json"))
    if not manifest_paths:
        return NormalizationSummary(
            processed=0,
            failed=1,
            pending_amendments=0,
            skipped=0,
            promoted=False,
            errors=("no canonical accession manifests found",),
        )

    normalized: list[_NormalizedFiling] = []
    errors: list[str] = []
    pending = 0
    skipped = 0
    failed = 0
    seen_verified_ciks: set[int] = set()
    for manifest_path in manifest_paths:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest root is not an object")
        except (OSError, ValueError) as exc:
            failed += 1
            errors.append(f"{manifest_path}: invalid manifest: {exc}")
            continue

        accession = str(manifest.get("accession") or manifest_path.stem)
        try:
            cik = int(manifest.get("cik"))
        except (TypeError, ValueError):
            failed += 1
            errors.append(f"{accession}: invalid or missing CIK")
            continue
        if cik not in verified:
            skipped += 1
            continue
        seen_verified_ciks.add(cik)
        expected_cik_dir = f"{cik:010d}"
        expected_accession_stem = accession.replace("-", "")
        if (
            manifest_path.parent.name != expected_cik_dir
            or manifest_path.stem != expected_accession_stem
        ):
            failed += 1
            errors.append(f"{accession}: canonical manifest identity mismatch")
            continue
        status = str(manifest.get("status") or "")
        if status not in KNOWN_MANIFEST_STATUSES:
            failed += 1
            errors.append(f"{accession}: unknown manifest status {status!r}")
            continue
        if status != "OK":
            failed += 1
            errors.append(f"{accession}: manifest status is {status}")
            continue

        components = manifest.get("components")
        if not isinstance(components, dict):
            failed += 1
            errors.append(f"{accession}: missing component metadata")
            continue
        primary = components.get("primary_document")
        information_table = components.get("information_table")
        if not isinstance(primary, dict):
            failed += 1
            errors.append(f"{accession}: missing primary document component")
            continue
        if not isinstance(information_table, dict):
            failed += 1
            errors.append(f"{accession}: missing information table component")
            continue

        try:
            primary_bytes = _read_component(store, accession, primary)
            info_bytes = _read_component(store, accession, information_table)
        except (OSError, RuntimeError, ValueError) as exc:
            failed += 1
            errors.append(f"{accession}: component checksum/read failure: {exc}")
            continue
        if str(manifest.get("checksum") or "") != str(
            information_table.get("checksum") or ""
        ):
            failed += 1
            errors.append(f"{accession}: top-level information checksum mismatch")
            continue
        if (
            not manifest.get("accepted_at")
            or not information_table.get("fetched_at_utc")
            or not primary.get("fetched_at_utc")
        ):
            failed += 1
            errors.append(f"{accession}: missing acquisition timestamp metadata")
            continue

        form_type = str(manifest.get("form_type") or "")
        if form_type not in {"13F-HR", "13F-HR/A"}:
            failed += 1
            errors.append(f"{accession}: unsupported form type {form_type!r}")
            continue
        try:
            _validate_timestamp(str(manifest.get("accepted_at") or ""))
            _validate_timestamp(
                str(information_table.get("fetched_at_utc") or "")
            )
            _validate_timestamp(str(primary.get("fetched_at_utc") or ""))
            info_path = _component_path(information_table)
            cover_path = _component_path(primary)
        except ValueError as exc:
            failed += 1
            errors.append(f"{accession}: invalid provenance metadata: {exc}")
            continue
        try:
            cover = parse_cover_page(primary_bytes)
        except XmlParseError as exc:
            if form_type.endswith("/A"):
                pending += 1
                errors.append(f"{accession}: amendment metadata pending: {exc}")
            else:
                failed += 1
                errors.append(f"{accession}: invalid cover page: {exc}")
            continue
        if cover.submission_type != form_type:
            failed += 1
            errors.append(
                f"{accession}: cover form {cover.submission_type!r} "
                f"does not match manifest {form_type!r}"
            )
            continue
        if cover.report_period != str(manifest.get("report_date") or ""):
            failed += 1
            errors.append(f"{accession}: cover report period mismatch")
            continue
        try:
            rows = tuple(parse_info_table(info_bytes))
        except XmlParseError as exc:
            failed += 1
            errors.append(f"{accession}: invalid information table: {exc}")
            continue

        normalized.append(
            _NormalizedFiling(
                manifest=manifest,
                cover=cover,
                rows=rows,
                info_checksum=str(information_table["checksum"]),
                info_path=info_path,
                cover_checksum=str(primary["checksum"]),
                cover_path=cover_path,
                fetched_at_utc=str(information_table["fetched_at_utc"]),
                source_url=str(
                    information_table.get("final_url")
                    or information_table.get("source_url")
                    or manifest.get("source_url")
                    or ""
                ),
            )
        )

    missing_ciks = sorted(set(verified) - seen_verified_ciks)
    if missing_ciks:
        failed += len(missing_ciks)
        errors.extend(
            f"CIK {cik:010d}: no accession manifest found" for cik in missing_ciks
        )

    if failed or pending:
        return NormalizationSummary(
            processed=len(normalized),
            failed=failed,
            pending_amendments=pending,
            skipped=skipped,
            promoted=False,
            errors=tuple(errors),
        )

    staging_path = _new_staging_path(db_path)
    try:
        _build_database(
            staging_path,
            normalized,
            verified,
            mappings_path=mappings_path,
            scoring_path=scoring_path,
            methodology_version=methodology_version,
        )
        _assert_no_live_sidecars(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging_path, db_path)
    except Exception as exc:  # fail closed at the promotion boundary
        errors.append(f"database build/promotion failed: {exc}")
        _remove_sqlite_files(staging_path)
        return NormalizationSummary(
            processed=len(normalized),
            failed=1,
            pending_amendments=0,
            skipped=skipped,
            promoted=False,
            errors=tuple(errors),
        )
    _remove_sqlite_sidecars(staging_path)
    return NormalizationSummary(
        processed=len(normalized),
        failed=0,
        pending_amendments=0,
        skipped=skipped,
        promoted=True,
        errors=(),
    )


def _read_component(store: RawStore, accession: str, component: dict) -> bytes:
    checksum = str(component.get("checksum") or "")
    object_path = str(component.get("object_path") or "")
    if len(checksum) != 64 or not object_path:
        raise ValueError(f"{accession}: incomplete object identity")
    return store.read_object(object_path, checksum)


def _component_path(component: dict) -> str:
    value = str(component.get("logical_path") or component.get("object_path") or "")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe component path {value!r}")
    return path.as_posix()


def _validate_timestamp(value: str) -> None:
    if not value:
        raise ValueError("missing timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp {value!r}") from exc


def _load_verified_managers(path: Path) -> dict[int, dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(
            line for line in handle if not line.lstrip().startswith("#")
        )
        return {
            int(row["cik"]): row
            for row in rows
            if row.get("validation_status") in {"VERIFIED", "VERIFIED_WITH_SCOPE"}
        }


def _new_staging_path(db_path: Path) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{db_path.name}.",
        suffix=".staging",
        dir=db_path.parent,
    )
    os.close(descriptor)
    path = Path(name)
    path.unlink()
    return path


def _build_database(
    path: Path,
    normalized: list[_NormalizedFiling],
    verified: dict[int, dict],
    *,
    mappings_path: Path,
    scoring_path: Path,
    methodology_version: str,
) -> None:
    conn = connect(path)
    try:
        init_db(conn)
        manager_ids: dict[int, int] = {}
        for cik, row in sorted(verified.items()):
            manager_ids[cik] = upsert_manager(
                conn,
                name=row.get("official_filer_name") or row["label"],
                cik=cik,
                notes=row.get("notes") or "",
            )
        mappings = load_mappings(mappings_path)
        mapping_dates = [item.verified_at for item in mappings.values() if item.verified_at]
        mapping_date = max(mapping_dates, default="UNKNOWN")

        for item in sorted(
            normalized,
            key=lambda value: (
                int(value.manifest["cik"]),
                value.cover.report_period,
                str(value.manifest["accepted_at"]),
                str(value.manifest["accession"]),
            ),
        ):
            manifest = item.manifest
            cik = int(manifest["cik"])
            manager_id = manager_ids[cik]
            is_amendment = item.cover.amendment_type is not None
            filing_id = upsert_filing(
                conn,
                manager_id=manager_id,
                report_period=item.cover.report_period,
                filing_date=str(manifest["filing_date"]),
                accession_number=str(manifest["accession"]),
                form_type=item.cover.submission_type,
                is_amendment=is_amendment,
                source_url=item.source_url,
                raw_checksum=item.info_checksum,
                raw_path=item.info_path,
                fetched_at_utc=item.fetched_at_utc,
                ingest_status="OK",
                accepted_at=str(manifest["accepted_at"]),
                amendment_number=item.cover.amendment_number,
                amendment_type=item.cover.amendment_type,
                amendment_status="PARSED" if is_amendment else "NOT_APPLICABLE",
                cover_checksum=item.cover_checksum,
                cover_raw_path=item.cover_path,
            )
            replace_holdings(
                conn,
                filing_id=filing_id,
                manager_id=manager_id,
                report_period=item.cover.report_period,
                rows=item.rows,
                commit=False,
            )
            security_rows: list[tuple] = []
            unresolved: set[str] = set()
            for row in item.rows:
                mapping = resolve(mappings, row.cusip)
                security_rows.append(
                    (
                        mapping.cusip,
                        mapping.ticker,
                        mapping.issuer or row.name_of_issuer or None,
                        mapping.share_class or row.title_of_class or None,
                        mapping.mapping_status,
                        mapping.mapping_source,
                    )
                )
                if mapping.mapping_status == "UNRESOLVED":
                    unresolved.add(mapping.cusip)
            bulk_ensure_securities(
                conn,
                security_rows,
                mapping_date=mapping_date,
                commit=False,
            )
            backfill_holding_tickers(conn, filing_id=filing_id, commit=False)
            if unresolved:
                add_quality_event(
                    conn,
                    event_type="UNRESOLVED_CUSIP",
                    severity="WARN",
                    message=(
                        f"{len(unresolved)} unresolved CUSIPs: "
                        + ", ".join(sorted(unresolved)[:20])
                    ),
                    manager_id=manager_id,
                    report_period=item.cover.report_period,
                    filing_id=filing_id,
                    commit=False,
                )
            conn.commit()

        _link_amendment_predecessors(conn)
        compute_portfolio_weights(conn)
        if scoring_path.exists():
            apply_scoring(
                conn,
                scoring_path,
                methodology_version=methodology_version,
            )
        compute_position_changes(conn, methodology_version)
        compute_consensus(conn, methodology_version=methodology_version)
        compute_trends(conn, methodology_version=methodology_version)
        run_quality_checks(conn, methodology_version)

        blocked = conn.execute(
            """
            SELECT COUNT(*) FROM effective_periods
            WHERE methodology_version=? AND status!='READY'
            """,
            (methodology_version,),
        ).fetchone()[0]
        if blocked:
            raise RuntimeError(f"{blocked} effective periods are not READY")
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise RuntimeError(f"foreign key violations: {foreign_keys[:5]}")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _link_amendment_predecessors(conn: sqlite3.Connection) -> None:
    groups = conn.execute(
        """
        SELECT DISTINCT manager_id, report_period FROM filings
        ORDER BY manager_id, report_period
        """
    ).fetchall()
    for manager_id, report_period in groups:
        rows = conn.execute(
            """
            SELECT filing_id, is_amendment
            FROM filings WHERE manager_id=? AND report_period=?
            ORDER BY accepted_at, filing_date, accession_number
            """,
            (manager_id, report_period),
        ).fetchall()
        predecessor = None
        for filing_id, is_amendment in rows:
            conn.execute(
                "UPDATE filings SET amends_filing_id=? WHERE filing_id=?",
                (predecessor if is_amendment else None, filing_id),
            )
            predecessor = filing_id
    conn.commit()


def _assert_no_live_sidecars(db_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.exists():
            raise RuntimeError(f"target database has live sidecar: {sidecar.name}")


def _remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _remove_sqlite_files(path: Path) -> None:
    path.unlink(missing_ok=True)
    _remove_sqlite_sidecars(path)
