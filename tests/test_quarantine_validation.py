"""Independent audit of synthetic quarantined raw; not human Gate 2 approval."""
import json
import sqlite3

import pytest

from test_normalization import _quarantine_case, _with_quarantine
from thirteenf.validation.gate_context import GateBundle


def _bundle(tmp_path):
    raw, policy = _quarantine_case(tmp_path)
    result = _with_quarantine(tmp_path, raw, policy)
    assert result.promoted, result.errors
    return GateBundle(raw, tmp_path / "candidate.db", "0.1.1", quarantine_policy_path=policy)


def test_independent_quarantine_audit_preserves_raw_not_production_parser(tmp_path, monkeypatch):
    from thirteenf.validation.quarantine import audit_quarantine
    bundle = _bundle(tmp_path)
    import thirteenf.parser as production
    monkeypatch.setattr(production, "parse_info_table", lambda _: (_ for _ in ()).throw(AssertionError("production parser called")))
    result = audit_quarantine(bundle)
    assert result["status"] == "PASS"
    assert result["source_filings"] == 1
    assert result["checked_raw_rows"] == 1
    assert result["manager_periods"] == [[1, "2026-06-30"]]


@pytest.mark.parametrize("sql", [
    "UPDATE holdings SET shares=shares+1",
    "UPDATE holdings SET portfolio_weight=1",
    "UPDATE holdings SET investment_discretion='OTHER'",
    "UPDATE holdings SET other_manager='999'",
    "UPDATE filings SET ingest_status='OK'",
    "DELETE FROM quality_events WHERE event_type='SOURCE_QUARANTINED'",
    "UPDATE effective_periods SET status='READY'",
    "UPDATE effective_periods SET total_value=1000",
    "DELETE FROM effective_periods",
])
def test_quarantine_audit_detects_corruption(tmp_path, sql):
    from thirteenf.validation.quarantine import audit_quarantine
    bundle = _bundle(tmp_path)
    conn = sqlite3.connect(bundle.db_path)
    conn.execute(sql)
    conn.commit()
    conn.close()
    result = audit_quarantine(bundle)
    assert result["status"] == "FAIL"
    assert result["errors"]


def test_quarantine_without_policy_never_passes(tmp_path):
    from thirteenf.validation.quarantine import audit_quarantine
    bundle = _bundle(tmp_path)
    result = audit_quarantine(GateBundle(bundle.raw_root, bundle.db_path, "0.1.1"))
    assert result["status"] == "FAIL"


@pytest.mark.parametrize("payload", ['[{"manager_id":1}]', 'invalid-json', '[{}]'])
def test_quarantine_audit_rejects_consensus_leak(tmp_path, payload):
    from thirteenf.validation.quarantine import audit_quarantine
    bundle = _bundle(tmp_path)
    conn = sqlite3.connect(bundle.db_path)
    conn.execute("INSERT INTO consensus_scores(security_id,report_period,put_call,shares_type,manager_count,"
                 "raw_contributions,consensus_score,methodology_version) VALUES(1,'2026-06-30','','SH',1,?,0.5,'0.1.1')", (payload,))
    conn.commit()
    conn.close()
    result = audit_quarantine(bundle)
    assert result["status"] == "FAIL"


def test_independent_gates_accept_exclusion_but_never_relax_sample_minimum(tmp_path):
    from thirteenf.validation.gate1 import run_gate1
    from thirteenf.validation.gate2 import run_gate2
    bundle = _bundle(tmp_path)
    for result in (run_gate1(bundle), run_gate2(bundle)):
        assert not result.passed  # One quarantined synthetic filing is not 150/30 validation.
        assert result.quarantine["status"] == "PASS"
        assert not any(m["kind"] in ("period_inventory", "effective_period", "source_quarantine")
                       for m in result.mismatches)
