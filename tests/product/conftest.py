"""Self-contained synthetic schema-v3 product bundle for UI/query tests."""

from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.changes import compute_position_changes
from thirteenf.database import (
    add_quality_event,
    connect,
    ensure_security,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)
from thirteenf.parser import AmendmentType
from thirteenf.product.evidence import ProductStore


METHODOLOGY_VERSION = "0.1.0"


@dataclass(frozen=True)
class ProductBundle:
    root: Path
    db: Path
    resolution: Path
    semantic: Path
    managers: Path


class _Row:
    def __init__(
        self,
        ordinal: int,
        security: dict,
        shares: int,
        value: int,
        *,
        put_call: str = "",
        discretion: str = "SOLE",
    ) -> None:
        self.row_ordinal = ordinal
        self.cusip = security["cusip"]
        self.name_of_issuer = security["issuer"]
        self.title_of_class = security.get("title_of_class") or "COM"
        self.put_call = put_call
        self.ssh_prnamt_type = "SH"
        self.investment_discretion = discretion
        self.other_manager = ""
        self.shares = shares
        self.value = value


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _selected_securities(resolution: Path, semantic: Path) -> list[dict]:
    resolution_rows = _read_csv(resolution)
    semantic_rows = _read_csv(semantic)
    by_cusip = {row["cusip"]: row for row in resolution_rows}
    selected = {
        "02079K305",  # GOOGL
        "02079K107",  # GOOG
        "037833100",  # AAPL
        "594918104",  # MSFT
        "68243Q106",  # 1-800-FLOWERS
    }

    seen_status: set[str] = set()
    for row in resolution_rows:
        status = row.get("status", "")
        if status and status not in seen_status:
            selected.add(row["cusip"])
            seen_status.add(status)

    seen_type: set[str] = set()
    for row in semantic_rows:
        economic_type = row.get("economic_type", "")
        if (
            economic_type
            and economic_type not in seen_type
            and row["cusip"] in by_cusip
        ):
            selected.add(row["cusip"])
            seen_type.add(economic_type)

    for row in resolution_rows:
        if row.get("symbol") and row.get("status", "").startswith("VERIFIED"):
            selected.add(row["cusip"])
        if len(selected) >= 48:
            break
    return [by_cusip[cusip] for cusip in sorted(selected) if cusip in by_cusip]


def _insert_filing(
    conn,
    manager_id: int,
    *,
    period: str,
    accession: str,
    accepted_at: str,
    rows: list[_Row],
    amendment_number: int | None = None,
    amendment_type: AmendmentType | None = None,
) -> int:
    is_amendment = amendment_type is not None
    filing_id = upsert_filing(
        conn,
        manager_id=manager_id,
        report_period=period,
        filing_date=accepted_at[:10],
        accession_number=accession,
        form_type="13F-HR/A" if is_amendment else "13F-HR",
        is_amendment=is_amendment,
        source_url=f"https://www.sec.gov/test/{accession}",
        raw_checksum=f"test-checksum-{accession}",
        raw_path=f"test-raw/{accession}/info_table.xml",
        fetched_at_utc="2026-09-05T00:00:00Z",
        ingest_status="OK",
        accepted_at=accepted_at,
        amendment_number=amendment_number,
        amendment_type=amendment_type,
        amendment_status="PARSED" if is_amendment else "NOT_APPLICABLE",
    )
    replace_holdings(
        conn,
        filing_id=filing_id,
        manager_id=manager_id,
        report_period=period,
        rows=rows,
    )
    return filing_id


def _build_bundle(root: Path) -> ProductBundle:
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "thirteenf-test.db"
    resolution = ROOT / "reports" / "research" / "security_resolution_master.csv"
    semantic = ROOT / "reports" / "research" / "security_semantic_classification.csv"
    managers_path = ROOT / "config" / "managers.csv"

    securities = _selected_securities(resolution, semantic)
    security_by_cusip = {row["cusip"]: row for row in securities}
    anchors = [
        row
        for row in securities
        if row["cusip"]
        not in {"02079K305", "02079K107", "037833100", "594918104"}
    ]
    managers = [
        row
        for row in _read_csv(managers_path)
        if row.get("validation_status") in {"VERIFIED", "VERIFIED_WITH_SCOPE"}
    ]

    conn = connect(db_path)
    init_db(conn)
    for security in securities:
        ensure_security(
            conn,
            cusip=security["cusip"],
            ticker=security.get("symbol") or None,
            issuer=security.get("issuer") or None,
            share_class=security.get("title_of_class") or None,
            mapping_status=security.get("status") or "UNRESOLVED",
            mapping_source="SYNTHETIC_TEST_BUNDLE",
            mapping_date="2026-09-05",
        )

    for index, manager in enumerate(managers):
        manager_id = upsert_manager(
            conn,
            name=manager["official_filer_name"],
            cik=int(manager["cik"]),
            notes="synthetic product test bundle",
        )
        token = f"{index + 1:010d}"
        if index == 0:
            q1_rows = [
                _Row(1, security_by_cusip["02079K305"], 100, 1000),
                _Row(
                    2,
                    security_by_cusip["02079K107"],
                    5,
                    500,
                    put_call="CALL",
                ),
                _Row(3, security_by_cusip["037833100"], 20, 200),
            ]
            q2_rows = [
                _Row(1, security_by_cusip["02079K305"], 75, 750),
                _Row(
                    2,
                    security_by_cusip["02079K305"],
                    75,
                    750,
                    discretion="SHARED",
                ),
                _Row(
                    3,
                    security_by_cusip["02079K107"],
                    5,
                    500,
                    put_call="CALL",
                ),
            ]
            _insert_filing(
                conn,
                manager_id,
                period="2026-03-31",
                accession=f"{token}-26-000001",
                accepted_at="2026-05-10T10:00:00Z",
                rows=q1_rows,
            )
            _insert_filing(
                conn,
                manager_id,
                period="2026-06-30",
                accession=f"{token}-26-000002",
                accepted_at="2026-08-10T10:00:00Z",
                rows=q2_rows,
            )
            _insert_filing(
                conn,
                manager_id,
                period="2026-06-30",
                accession=f"{token}-26-000003",
                accepted_at="2026-08-11T10:00:00Z",
                rows=[_Row(1, security_by_cusip["594918104"], 30, 3000)],
                amendment_number=1,
                amendment_type=AmendmentType.ADD_NEW_HOLDINGS,
            )
            continue

        anchor = anchors[(index - 1) % len(anchors)]
        q1_rows = [_Row(1, anchor, 10 + index, 100 + index)]
        q2_rows = [_Row(1, anchor, 10 + index, 100 + index)]
        mode = index % 5
        if mode != 0:
            q1_shares = 150 if mode == 2 else 100
            q1_rows.append(
                _Row(2, security_by_cusip["02079K305"], q1_shares, q1_shares * 10)
            )
        if mode != 3:
            q2_shares = 150 if mode == 1 else 100
            q2_rows.append(
                _Row(2, security_by_cusip["02079K305"], q2_shares, q2_shares * 10)
            )
        _insert_filing(
            conn,
            manager_id,
            period="2026-03-31",
            accession=f"{token}-26-000001",
            accepted_at="2026-05-10T10:00:00Z",
            rows=q1_rows,
        )
        _insert_filing(
            conn,
            manager_id,
            period="2026-06-30",
            accession=f"{token}-26-000002",
            accepted_at="2026-08-10T10:00:00Z",
            rows=q2_rows,
        )

    compute_position_changes(conn, METHODOLOGY_VERSION)
    add_quality_event(
        conn,
        event_type="INCOMPLETE_QUARTER",
        severity="WARN",
        message="synthetic product test quality state",
    )
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    (data_dir / "last_update.json").write_text(
        json.dumps(
            {
                "success": True,
                "last_update_finished_at": "2026-09-05T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return ProductBundle(root, db_path, resolution, semantic, managers_path)


@pytest.fixture(scope="session")
def product_bundle(tmp_path_factory) -> ProductBundle:
    return _build_bundle(tmp_path_factory.mktemp("product-bundle"))


@pytest.fixture(scope="session", autouse=True)
def product_environment(product_bundle):
    values = {
        "THIRTEENF_DB_PATH": str(product_bundle.db),
        "THIRTEENF_RESOLUTION_CSV": str(product_bundle.resolution),
        "THIRTEENF_SEMANTIC_CSV": str(product_bundle.semantic),
        "THIRTEENF_MANAGERS_CSV": str(product_bundle.managers),
    }
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="session")
def store(product_bundle, product_environment):
    evidence_store = ProductStore(
        product_bundle.db,
        product_bundle.resolution,
        product_bundle.semantic,
        product_bundle.managers,
    )
    yield evidence_store
    evidence_store.close()


@pytest.fixture(scope="session")
def repo_root():
    return ROOT
