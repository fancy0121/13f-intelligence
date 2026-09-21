from __future__ import annotations

import hashlib
import shutil
import sqlite3
from collections import Counter

from thirteenf.validation.gate2 import run_gate2
from thirteenf.validation.gate_context import GateBundle


def test_gate2_detects_missing_effective_period(sample_bundle, tmp_path):
    copied = tmp_path / "dropped-period.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute("DELETE FROM effective_periods WHERE effective_period_id=(SELECT MAX(effective_period_id) FROM effective_periods)")
    conn.commit()
    conn.close()
    result = run_gate2(GateBundle(sample_bundle.raw_root, copied, "0.1.0"))
    assert any(item["kind"] == "period_inventory" for item in result.mismatches)


def test_gate2_detects_changed_acceptance_timestamp(sample_bundle, tmp_path):
    copied = tmp_path / "changed-time.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute("UPDATE filings SET accepted_at='2026-08-14T10:00:01Z' WHERE filing_id=(SELECT MAX(filing_id) FROM filings)")
    conn.commit()
    conn.close()
    result = run_gate2(GateBundle(sample_bundle.raw_root, copied, "0.1.0"))
    assert any(item.get("field") == "accepted_at" for item in result.mismatches)


def test_gate2_checks_filing_date_used_for_value_units(sample_bundle, tmp_path):
    copied = tmp_path / "changed-date.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute("UPDATE filings SET filing_date='2022-11-14' WHERE filing_id=(SELECT MIN(filing_id) FROM filings)")
    conn.commit()
    conn.close()
    result = run_gate2(GateBundle(sample_bundle.raw_root, copied, "0.1.0"))
    assert not result.passed
    assert any(item.get("field") == "filing_date" for item in result.mismatches)


def test_gate2_does_not_reuse_production_unit_conversion(sample_bundle, tmp_path, monkeypatch):
    import thirteenf.effective as effective
    copied = tmp_path / "bad-conversion.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute("PRAGMA foreign_keys=ON")
    monkeypatch.setattr(effective, "reported_value_usd", lambda value, filing_date: value * 2)
    effective.rebuild_effective_positions(conn, "0.1.0")
    conn.commit()
    conn.close()
    result = run_gate2(GateBundle(sample_bundle.raw_root, copied, "0.1.0"))
    assert not result.passed
    assert any(item.get("field") == "value" for item in result.mismatches)


def test_gate2_replays_amendments_aggregates_and_checks_transitions(sample_bundle):
    before = hashlib.sha256(sample_bundle.db_path.read_bytes()).hexdigest()
    result = run_gate2(sample_bundle, min_transitions=30, min_managers=5)
    after = hashlib.sha256(sample_bundle.db_path.read_bytes()).hexdigest()
    assert result.passed
    assert result.checked_transitions >= 30
    assert len(result.manager_ids) >= 5
    assert result.period_pairs == (
        ("2025-12-31", "2026-03-31"),
        ("2026-03-31", "2026-06-30"),
    )
    assert result.mismatches == ()
    assert before == after
    counts = Counter(row["expected_change"] for row in result.review_rows)
    assert all(counts[change_type] for change_type in (
        "NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED"
    ))
    assert any(
        row["expected_change"] == "ADD"
        and row["expected_shares_now"] > row["expected_shares_prev"]
        and row["expected_weight_now"] < row["expected_weight_prev"]
        for row in result.review_rows
    )
    assert all("object_path" in row["raw_provenance"] for row in result.review_rows)


def test_gate2_detects_corrupt_aggregate(sample_bundle, tmp_path):
    copied = tmp_path / "corrupt-effective.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute(
        "UPDATE effective_positions SET shares=shares+1 "
        "WHERE effective_position_id=(SELECT MIN(effective_position_id) FROM effective_positions)"
    )
    conn.commit()
    conn.close()
    result = run_gate2(
        GateBundle(sample_bundle.raw_root, copied, "0.1.0"),
        min_transitions=30,
        min_managers=5,
    )
    assert not result.passed
    assert any(item["kind"] == "effective_position" for item in result.mismatches)


def test_gate2_detects_missing_add_new_holdings_component(sample_bundle, tmp_path):
    copied = tmp_path / "missing-supplement.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute(
        "DELETE FROM effective_filing_components WHERE component_role='SUPPLEMENT'"
    )
    conn.commit()
    conn.close()
    result = run_gate2(
        GateBundle(sample_bundle.raw_root, copied, "0.1.0"),
        min_transitions=30,
        min_managers=5,
    )
    assert not result.passed
    assert any(item["kind"] == "effective_component" for item in result.mismatches)


def test_gate2_detects_corrupt_weight_direction(sample_bundle, tmp_path):
    copied = tmp_path / "corrupt-weight.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute(
        "UPDATE position_changes SET weight_change=weight_change+0.01 "
        "WHERE change_id=(SELECT MIN(change_id) FROM position_changes "
        "WHERE weight_change IS NOT NULL)"
    )
    conn.commit()
    conn.close()
    result = run_gate2(
        GateBundle(sample_bundle.raw_root, copied, "0.1.0"),
        min_transitions=30,
        min_managers=5,
    )
    assert not result.passed
    assert any(
        item["kind"] == "position_change" and item.get("field") == "weight_change"
        for item in result.mismatches
    )


def test_gate2_detects_amendment_type_disagreement(sample_bundle, tmp_path):
    copied = tmp_path / "corrupt-amendment.db"
    shutil.copy2(sample_bundle.db_path, copied)
    conn = sqlite3.connect(copied)
    conn.execute(
        "UPDATE filings SET amendment_type='ADD_NEW_HOLDINGS' "
        "WHERE amendment_type='RESTATEMENT'"
    )
    conn.commit()
    conn.close()
    result = run_gate2(
        GateBundle(sample_bundle.raw_root, copied, "0.1.0"),
        min_transitions=30,
        min_managers=5,
    )
    assert not result.passed
    assert any(
        item["kind"] == "filing_metadata" and item.get("field") == "amendment_type"
        for item in result.mismatches
    )
