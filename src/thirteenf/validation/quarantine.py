"""Independent exclusion audit. Source numbers are checked, never repaired.

The production policy reader validates configuration syntax only; SEC facts
are independently parsed with the stdlib reference parser, not normalization.
The policy SHA is also bound into persisted event bytes and thus the Gate's DB hash.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET

from thirteenf.database import connect_readonly
from thirteenf.quarantine import load_policy
from thirteenf.validation.gate_context import GateBundle, component_bytes
from thirteenf.validation.reference_xml import reference_cover, reference_rows


def _controls(xml: bytes) -> tuple[int | None, int | None]:
    # Call only after reference_cover rejects DTD/entities/malformed input.
    root = ET.fromstring(xml)
    result = []
    for name in ("tableEntryTotal", "tableValueTotal"):
        nodes = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1] == name]
        if len(nodes) > 1:
            raise ValueError(f"duplicate {name}")
        result.append(int(nodes[0].text.strip()) if nodes else None)
    return tuple(result)


def audit_quarantine(bundle: GateBundle) -> dict:
    result = dict(status="PASS", policy_sha256=None, source_filings=0,
                  quarantined_filings=0, checked_raw_rows=0, manager_periods=[], errors=[])
    errors = result["errors"]
    conn = connect_readonly(bundle.db_path, immutable=True)
    conn.row_factory = sqlite3.Row
    try:
        policy = load_policy(bundle.quarantine_policy_path, bundle.methodology_version)
        entries = policy.get("entries", {})
        result["policy_sha256"] = policy.get("policy_sha256")
        filings = conn.execute("SELECT f.*,m.cik FROM filings f JOIN managers m ON m.manager_id=f.manager_id").fetchall()
        by_identity = {(int(f["cik"]), f["accession_number"]): f for f in filings}
        expected_periods = set()
        raw_cache = {}
        approved_filing_ids = set()
        for key, entry in entries.items():
            f = by_identity.get(key)
            if f is None:
                errors.append(f"approved source missing from DB: {key}")
                continue
            approved_filing_ids.add(f["filing_id"])
            expected_periods.add((f["manager_id"], entry["report_period"]))
            cover_bytes = component_bytes(bundle, *key, "primary_document")
            info_bytes = component_bytes(bundle, *key, "information_table")
            cover = reference_cover(cover_bytes)
            rows = reference_rows(info_bytes)
            raw_cache[key] = rows
            entry_total, value_total = _controls(cover_bytes)
            facts = dict(cik=key[0], accession=key[1], report_period=cover.report_period,
                         cover_sha256=hashlib.sha256(cover_bytes).hexdigest(),
                         info_sha256=hashlib.sha256(info_bytes).hexdigest(),
                         cover_entry_total=entry_total, info_row_count=len(rows),
                         cover_value_total_raw_units=value_total,
                         info_value_sum_raw_units=sum(r.value for r in rows))
            if any(entry[k] != v for k, v in facts.items()):
                errors.append(f"approved source/control identity mismatch: {key}")
            if not ((entry_total is not None and entry_total != len(rows))
                    or (value_total is not None and value_total != sum(r.value for r in rows))):
                errors.append(f"no independently observed contradiction: {key}")
            if (f["report_period"] != cover.report_period
                    or f["cover_checksum"] != facts["cover_sha256"]
                    or f["raw_checksum"] != facts["info_sha256"]):
                errors.append(f"filing provenance mismatch: {key}")
            events = conn.execute(
                "SELECT message,manager_id,report_period,severity FROM quality_events "
                "WHERE event_type='SOURCE_QUARANTINED' AND filing_id=?", (f["filing_id"],),
            ).fetchall()
            expected_event = {**facts, **{k: policy[k] for k in
                             ("policy_id", "policy_sha256", "methodology_version")}}
            if (len(events) != 1 or json.loads(events[0][0]) != expected_event
                    or tuple(events[0][1:]) != (f["manager_id"], f["report_period"], "ERROR")):
                errors.append(f"quarantine event does not bind approved policy and facts: {key}")
        if conn.execute("SELECT COUNT(*) FROM quality_events WHERE event_type='SOURCE_QUARANTINED'").fetchone()[0] != len(entries):
            errors.append("quarantine event inventory mismatch")
        actual_periods = {(f["manager_id"], f["report_period"]) for f in filings if f["ingest_status"] == "QUARANTINED"}
        if expected_periods != actual_periods:
            errors.append("quarantine period inventory differs from explicit approved policy")
        for f in filings:
            if (f["manager_id"], f["report_period"]) not in expected_periods | actual_periods:
                continue
            result["quarantined_filings"] += 1
            key = (int(f["cik"]), f["accession_number"])
            if f["ingest_status"] != "QUARANTINED":
                errors.append(f"whole-period exclusion missing: {key}")
            rows = raw_cache.get(key)
            if rows is None:
                rows = reference_rows(component_bytes(bundle, *key, "information_table"))
            db_rows = conn.execute(
                "SELECT row_ordinal,cusip,issuer,title_of_class,shares,value,put_call,ssh_prnamt_type,"
                "portfolio_weight,manager_id,report_period,investment_discretion,other_manager "
                "FROM holdings WHERE filing_id=? ORDER BY row_ordinal",
                (f["filing_id"],),
            ).fetchall()
            result["checked_raw_rows"] += len(rows)
            expected_rows = [(r.row_ordinal,r.cusip,r.issuer,r.title_of_class,r.shares,r.value,r.put_call,
                              r.shares_type,None,f["manager_id"],f["report_period"],
                              r.investment_discretion,r.other_manager) for r in rows]
            if [tuple(r) for r in db_rows] != expected_rows:
                errors.append(f"raw rows changed, missing, or carry an analytical weight: {key}")
        for mid, period in sorted(expected_periods | actual_periods):
            periods = conn.execute(
                "SELECT effective_period_id,status,total_value,methodology_version FROM effective_periods "
                "WHERE manager_id=? AND report_period=?", (mid, period),
            ).fetchall()
            if not any(p[3] == bundle.methodology_version for p in periods):
                errors.append(f"quarantined effective period missing: {mid}/{period}")
            for p in periods:
                if p[1] != "INCOMPLETE" or p[2] is not None:
                    errors.append(f"quarantined effective state is not INCOMPLETE/NULL: {mid}/{period}")
                for table in ("effective_positions", "effective_filing_components"):
                    if conn.execute(f"SELECT 1 FROM {table} WHERE effective_period_id=? LIMIT 1", (p[0],)).fetchone():
                        errors.append(f"quarantined data leaked into {table}: {mid}/{period}")
            if conn.execute("SELECT 1 FROM position_changes WHERE manager_id=? AND report_period=? LIMIT 1", (mid,period)).fetchone():
                errors.append(f"quarantined period has position changes: {mid}/{period}")
            for (encoded,) in conn.execute("SELECT raw_contributions FROM consensus_scores WHERE report_period=?", (period,)):
                contributions = json.loads(encoded)
                if (not isinstance(contributions, list) or any(
                        not isinstance(c, dict) or type(c.get("manager_id")) is not int
                        for c in contributions)):
                    errors.append(f"invalid consensus contribution identity: {period}")
                elif any(c["manager_id"] == mid for c in contributions):
                    errors.append(f"quarantined manager leaked into consensus: {mid}/{period}")
        result["source_filings"] = len(approved_filing_ids)
        result["manager_periods"] = [list(p) for p in sorted(expected_periods)]
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        conn.close()
    result["status"] = "FAIL" if errors else "PASS"
    return result
