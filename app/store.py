"""Shared ProductStore for the Streamlit UI (evidence only)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import streamlit as st

from thirteenf.product.evidence import (
    ProductStore,
    load_portfolio_rows,
    save_portfolio_rows,
)
from thirteenf.database import connect_readonly
from thirteenf.validation.gate_context import verify_public_snapshot

ROOT = Path(__file__).resolve().parents[1]
_REQUIRED_PRODUCT_TABLES = frozenset(
    {"effective_periods", "effective_positions", "effective_filing_components"}
)


def configured_database_path() -> Path:
    return Path(
        os.environ.get("THIRTEENF_DB_PATH", ROOT / "data" / "thirteenf.db")
    )


def configured_resolution_path() -> Path:
    return Path(os.environ.get(
        "THIRTEENF_RESOLUTION_CSV",
        ROOT / "reports" / "research" / "security_resolution_master.csv",
    ))


def configured_semantic_path() -> Path:
    return Path(os.environ.get(
        "THIRTEENF_SEMANTIC_CSV",
        ROOT / "reports" / "research" / "security_semantic_classification.csv",
    ))


def configured_managers_path() -> Path:
    return Path(os.environ.get("THIRTEENF_MANAGERS_CSV", ROOT / "config" / "managers.csv"))


def public_snapshot_error() -> str | None:
    if os.environ.get("THIRTEENF_PUBLIC_MODE", "").strip().lower() not in ("1", "true", "yes"):
        return None
    manifest = Path(os.environ.get("THIRTEENF_RELEASE_MANIFEST", ROOT / "release-manifest.json"))
    try:
        verify_public_snapshot(configured_database_path(), manifest, {
            "resolution": configured_resolution_path(),
            "semantic": configured_semantic_path(),
            "managers": configured_managers_path(),
        })
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError, sqlite3.Error):
        return "NOT_VALIDATED: public release evidence is missing, incomplete or does not match this snapshot"
    return None


def file_identity(path: Path | str) -> tuple[str, int | None, int | None]:
    """Stable cache input identity; missing files are distinct from present files."""
    candidate = Path(path).resolve()
    try:
        stat = candidate.stat()
    except OSError:
        return (str(candidate), None, None)
    return (str(candidate), stat.st_size, stat.st_mtime_ns)


def store_snapshot_key(
    db_path: Path | str,
    resolution_path: Path | str,
    semantic_path: Path | str,
    managers_path: Path | str,
    *,
    methodology_version: str | None,
) -> tuple[object, ...]:
    return (
        file_identity(db_path),
        file_identity(resolution_path),
        file_identity(semantic_path),
        file_identity(managers_path),
        methodology_version,
    )


def database_validation_error(path: Path | str) -> str | None:
    """Return a safe public error when a database cannot serve ProductStore."""
    candidate = Path(path)
    if not candidate.exists():
        return "NOT_VALIDATED: database file is missing"
    try:
        conn = connect_readonly(candidate, immutable=True)
        try:
            found = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        finally:
            conn.close()
    except sqlite3.Error:
        return "NOT_VALIDATED: database cannot be read"
    missing = sorted(_REQUIRED_PRODUCT_TABLES - found)
    if missing:
        return "NOT_VALIDATED: missing required schema tables: " + ", ".join(missing)
    return None


def default_private_portfolio_path(root: Path = ROOT) -> Path:
    return root / "data" / "private" / "portfolio.csv"


def load_local_portfolio(root: Path = ROOT) -> tuple[Path, list[dict]]:
    """Use the private store, copying legacy tracked holdings only once."""
    private_path = default_private_portfolio_path(root)
    private_rows = load_portfolio_rows(private_path)
    if private_rows or private_path.exists():
        return private_path, private_rows
    legacy_path = root / "config" / "portfolio.csv"
    legacy_rows = load_portfolio_rows(legacy_path)
    if legacy_rows:
        save_portfolio_rows(private_path, legacy_rows)
    return private_path, legacy_rows


@st.cache_resource
def _get_store(
    db_path: str,
    resolution_path: str,
    semantic_path: str,
    managers_path: str,
    methodology_version: str | None,
    snapshot: tuple[object, ...],
) -> ProductStore:
    return ProductStore(
        db_path,
        resolution_path,
        semantic_path,
        managers_path,
        methodology_version=methodology_version,
    )


def get_store() -> ProductStore:
    error = public_snapshot_error()
    if error:
        st.error("公开数据尚未通过发布验收。 [NOT_VALIDATED] / Public snapshot is not release-validated. [NOT_VALIDATED]")
        st.stop()
    db_path = configured_database_path()
    resolution_path = configured_resolution_path()
    semantic_path = configured_semantic_path()
    managers_path = configured_managers_path()
    methodology_version = os.environ.get("THIRTEENF_METHODOLOGY_VERSION")
    snapshot = store_snapshot_key(
        db_path,
        resolution_path,
        semantic_path,
        managers_path,
        methodology_version=methodology_version,
    )
    try:
        store = _get_store(
            str(db_path), str(resolution_path), str(semantic_path), str(managers_path),
            methodology_version, snapshot,
        )
        if os.environ.get("THIRTEENF_PUBLIC_MODE", "").strip().lower() not in ("1", "true", "yes"):
            st.warning(
                "本地研究候选版 [NOT_VALIDATED]：未声明完成公开发布验收。 / "
                "Local research candidate [NOT_VALIDATED]: not an attested public release."
            )
        quarantined = store.quarantined_periods()
        if quarantined:
            st.error(
                f"源数据隔离 [SOURCE_QUARANTINED]：{len(quarantined)} 个机构季度存在已核实的原文矛盾，"
                "不参与持仓变化、趋势或共识；缺失不等于零持仓。 / "
                f"{len(quarantined)} manager-quarters quarantined for confirmed source contradictions; "
                "excluded from analytics. Missing does not mean zero holdings."
            )
        return store
    except (sqlite3.Error, OSError, ValueError, RuntimeError, KeyError):
        # No internal filesystem paths or tracebacks in the public UI.
        st.error(
            "数据快照不可用，请联系维护人员。 [NOT_VALIDATED] / "
            "Data snapshot unavailable; contact the maintainer. [NOT_VALIDATED]"
        )
        st.stop()
