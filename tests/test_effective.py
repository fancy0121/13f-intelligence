from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import (
    connect,
    ensure_security,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)
from thirteenf.effective import (
    AmendmentPendingError,
    FilingVersion,
    load_effective_positions,
    rebuild_effective_positions,
    select_effective_components,
)
from thirteenf.parser import AmendmentType


class _Row:
    def __init__(
        self,
        ordinal,
        cusip,
        shares,
        value,
        *,
        put_call="",
        shares_type="SH",
        discretion="SOLE",
    ):
        self.row_ordinal = ordinal
        self.cusip = cusip
        self.name_of_issuer = f"ISSUER {cusip}"
        self.title_of_class = "COM"
        self.put_call = put_call
        self.ssh_prnamt_type = shares_type
        self.investment_discretion = discretion
        self.other_manager = ""
        self.shares = shares
        self.value = value


def _base(filing_id=1):
    return FilingVersion(
        filing_id=filing_id,
        accession_number=f"BASE-{filing_id}",
        accepted_at="2026-05-01T10:00:00Z",
        amendment_number=None,
        amendment_type=None,
        is_amendment=False,
    )


def _amendment(filing_id, number, amendment_type, accepted_at):
    return FilingVersion(
        filing_id=filing_id,
        accession_number=f"AMEND-{filing_id}",
        accepted_at=accepted_at,
        amendment_number=number,
        amendment_type=amendment_type,
        is_amendment=True,
    )


def test_addition_supplements_current_base():
    selection = select_effective_components(
        [
            _base(),
            _amendment(
                2,
                1,
                AmendmentType.ADD_NEW_HOLDINGS,
                "2026-05-02T10:00:00Z",
            ),
        ]
    )
    assert selection.base_filing_id == 1
    assert selection.supplement_filing_ids == (2,)
    assert len(selection.state_hash) == 64


def test_selection_hash_does_not_depend_on_database_surrogate_ids():
    versions = [
        _base(),
        _amendment(
            2,
            1,
            AmendmentType.ADD_NEW_HOLDINGS,
            "2026-05-02T10:00:00Z",
        ),
    ]
    remapped = [replace(item, filing_id=item.filing_id + 100) for item in versions]
    assert (
        select_effective_components(versions).state_hash
        == select_effective_components(remapped).state_hash
    )


def test_later_restatement_resets_prior_supplements():
    selection = select_effective_components(
        [
            _base(),
            _amendment(
                2,
                1,
                AmendmentType.ADD_NEW_HOLDINGS,
                "2026-05-02T10:00:00Z",
            ),
            _amendment(
                3,
                2,
                AmendmentType.RESTATEMENT,
                "2026-05-03T10:00:00Z",
            ),
            _amendment(
                4,
                3,
                AmendmentType.ADD_NEW_HOLDINGS,
                "2026-05-04T10:00:00Z",
            ),
        ]
    )
    assert selection.base_filing_id == 3
    assert selection.supplement_filing_ids == (4,)


def test_unknown_amendment_blocks_selection():
    unknown = _amendment(2, 1, None, "2026-05-02T10:00:00Z")
    with pytest.raises(AmendmentPendingError, match="metadata"):
        select_effective_components([_base(), unknown])


def _database(tmp_path):
    conn = connect(tmp_path / "effective.db")
    init_db(conn)
    manager_id = upsert_manager(conn, name="MANAGER", cik=1)
    return conn, manager_id


def _security(conn, cusip):
    return ensure_security(
        conn,
        cusip=cusip,
        ticker=cusip[:3],
        issuer=f"ISSUER {cusip}",
        share_class="COM",
        mapping_status="VERIFIED",
        mapping_source="MANUAL_REVIEW",
        mapping_date="2026-09-05",
    )


def _filing(
    conn,
    manager_id,
    *,
    accession,
    accepted_at,
    rows,
    is_amendment=False,
    amendment_number=None,
    amendment_type=None,
    amendment_status=None,
):
    filing_id = upsert_filing(
        conn,
        manager_id=manager_id,
        report_period="2026-03-31",
        filing_date=accepted_at[:10],
        accession_number=accession,
        form_type="13F-HR/A" if is_amendment else "13F-HR",
        is_amendment=is_amendment,
        source_url=f"https://www.sec.gov/{accession}",
        raw_checksum=f"checksum-{accession}",
        raw_path=f"raw/{accession}/info_table.xml",
        fetched_at_utc="2026-09-05T00:00:00Z",
        ingest_status="OK",
        accepted_at=accepted_at,
        amendment_number=amendment_number,
        amendment_type=amendment_type,
        amendment_status=amendment_status,
    )
    replace_holdings(
        conn,
        filing_id=filing_id,
        manager_id=manager_id,
        report_period="2026-03-31",
        rows=rows,
    )
    return filing_id


def test_rebuild_aggregates_economic_keys_and_preserves_provenance(tmp_path):
    conn, manager_id = _database(tmp_path)
    sid_a = _security(conn, "AAAA11111")
    sid_b = _security(conn, "BBBB22222")
    base_id = _filing(
        conn,
        manager_id,
        accession="BASE",
        accepted_at="2026-05-01T10:00:00Z",
        rows=[
            _Row(1, "AAAA11111", 100, 1000, discretion="SOLE"),
            _Row(2, "AAAA11111", 200, 2000, discretion="SHARED"),
            _Row(3, "AAAA11111", 5, 500, put_call="CALL"),
            _Row(4, "AAAA11111", 7, 700, put_call="PUT"),
            _Row(5, "AAAA11111", 1000, 100, shares_type="PRN"),
        ],
    )
    supplement_id = _filing(
        conn,
        manager_id,
        accession="ADD",
        accepted_at="2026-05-02T10:00:00Z",
        rows=[_Row(1, "BBBB22222", 50, 5000)],
        is_amendment=True,
        amendment_number=1,
        amendment_type=AmendmentType.ADD_NEW_HOLDINGS,
        amendment_status="PARSED",
    )

    assert rebuild_effective_positions(conn, "0.1.0") == 5
    positions = load_effective_positions(conn, manager_id, "2026-03-31")
    assert positions[(sid_a, "", "SH")].shares == 300
    assert positions[(sid_a, "", "SH")].value == 3000
    assert positions[(sid_a, "CALL", "SH")].shares == 5
    assert positions[(sid_a, "PUT", "SH")].shares == 7
    assert positions[(sid_a, "", "PRN")].shares == 1000
    assert positions[(sid_b, "", "SH")].shares == 50
    assert positions[(sid_a, "", "SH")].portfolio_weight == pytest.approx(
        3000 / 9300
    )
    assert positions[(sid_a, "", "SH")].provenance == (
        (base_id, 1),
        (base_id, 2),
    )

    components = conn.execute(
        """
        SELECT filing_id, component_role, sequence
        FROM effective_filing_components ORDER BY sequence
        """
    ).fetchall()
    assert [tuple(row) for row in components] == [
        (base_id, "BASE", 0),
        (supplement_id, "SUPPLEMENT", 1),
    ]
    stored = conn.execute(
        "SELECT provenance_json FROM effective_positions WHERE security_id=? AND put_call='' AND shares_type='SH'",
        (sid_a,),
    ).fetchone()[0]
    assert json.loads(stored) == [
        {"filing_id": base_id, "row_ordinal": 1},
        {"filing_id": base_id, "row_ordinal": 2},
    ]
    conn.close()


def test_restatement_discards_old_base_and_supplement_rows(tmp_path):
    conn, manager_id = _database(tmp_path)
    sid_a = _security(conn, "AAAA11111")
    sid_b = _security(conn, "BBBB22222")
    sid_c = _security(conn, "CCCC33333")
    _filing(
        conn,
        manager_id,
        accession="BASE",
        accepted_at="2026-05-01T10:00:00Z",
        rows=[_Row(1, "AAAA11111", 100, 1000)],
    )
    _filing(
        conn,
        manager_id,
        accession="ADD1",
        accepted_at="2026-05-02T10:00:00Z",
        rows=[_Row(1, "BBBB22222", 50, 500)],
        is_amendment=True,
        amendment_number=1,
        amendment_type=AmendmentType.ADD_NEW_HOLDINGS,
        amendment_status="PARSED",
    )
    restatement_id = _filing(
        conn,
        manager_id,
        accession="RESTATE",
        accepted_at="2026-05-03T10:00:00Z",
        rows=[_Row(1, "AAAA11111", 200, 2000)],
        is_amendment=True,
        amendment_number=2,
        amendment_type=AmendmentType.RESTATEMENT,
        amendment_status="PARSED",
    )
    final_add_id = _filing(
        conn,
        manager_id,
        accession="ADD2",
        accepted_at="2026-05-04T10:00:00Z",
        rows=[_Row(1, "CCCC33333", 25, 250)],
        is_amendment=True,
        amendment_number=3,
        amendment_type=AmendmentType.ADD_NEW_HOLDINGS,
        amendment_status="PARSED",
    )

    rebuild_effective_positions(conn, "0.1.0")
    positions = load_effective_positions(conn, manager_id, "2026-03-31")
    assert positions[(sid_a, "", "SH")].shares == 200
    assert (sid_b, "", "SH") not in positions
    assert positions[(sid_c, "", "SH")].shares == 25
    components = conn.execute(
        "SELECT filing_id, component_role FROM effective_filing_components ORDER BY sequence"
    ).fetchall()
    assert [tuple(row) for row in components] == [
        (restatement_id, "BASE"),
        (final_add_id, "SUPPLEMENT"),
    ]
    conn.close()


def test_pending_amendment_materializes_no_positions(tmp_path):
    conn, manager_id = _database(tmp_path)
    _security(conn, "AAAA11111")
    _filing(
        conn,
        manager_id,
        accession="BASE",
        accepted_at="2026-05-01T10:00:00Z",
        rows=[_Row(1, "AAAA11111", 100, 1000)],
    )
    _filing(
        conn,
        manager_id,
        accession="UNKNOWN",
        accepted_at="2026-05-02T10:00:00Z",
        rows=[_Row(1, "AAAA11111", 10, 100)],
        is_amendment=True,
        amendment_number=1,
        amendment_status="AMENDMENT_PENDING",
    )

    assert rebuild_effective_positions(conn, "0.1.0") == 0
    status = conn.execute(
        "SELECT status FROM effective_periods"
    ).fetchone()[0]
    assert status == "AMENDMENT_PENDING"
    assert conn.execute("SELECT COUNT(*) FROM effective_positions").fetchone()[0] == 0
    conn.close()
