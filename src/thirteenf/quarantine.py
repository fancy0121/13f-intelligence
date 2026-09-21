"""Exact, owner-approved source exceptions. Exclusion is not source repair."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


IDENTITY_FIELDS = ("cik", "accession", "report_period", "cover_sha256", "info_sha256")
CONTROL_FIELDS = ("cover_entry_total", "info_row_count",
                  "cover_value_total_raw_units", "info_value_sum_raw_units")


def load_policy(path: Path | str | None, methodology_version: str) -> dict:
    if path is None:
        return {}
    raw = Path(path).read_bytes()
    policy = json.loads(raw)
    if (not isinstance(policy, dict)
            or policy.get("methodology_version") != methodology_version
            or policy.get("action") != "QUARANTINE_MANAGER_PERIOD"
            or not isinstance(policy.get("policy_id"), str) or not policy["policy_id"]
            or not isinstance(policy.get("entries"), list) or not policy["entries"]):
        raise ValueError("invalid quarantine policy or methodology mismatch")
    entries = {}
    for entry in policy["entries"]:
        if not isinstance(entry, dict) or any(k not in entry for k in IDENTITY_FIELDS + CONTROL_FIELDS):
            raise ValueError("quarantine entry lacks exact source/control identity")
        if type(entry["cik"]) is not int or entry["cik"] <= 0:
            raise ValueError("invalid quarantine CIK")
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", str(entry["accession"])):
            raise ValueError("invalid quarantine accession")
        for field in ("cover_sha256", "info_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry[field])):
                raise ValueError("invalid quarantine checksum")
        for field in CONTROL_FIELDS:
            if entry[field] is not None and (type(entry[field]) is not int or entry[field] < 0):
                raise ValueError("invalid quarantine control total")
        key = (entry["cik"], entry["accession"])
        if key in entries:
            raise ValueError("duplicate quarantine identity")
        entries[key] = entry
    return dict(policy_id=policy["policy_id"], methodology_version=methodology_version,
                policy_sha256=hashlib.sha256(raw).hexdigest(), entries=entries)


def check_source(policy: dict, observed: dict) -> dict | None:
    """Reject every unknown discrepancy and every changed approved source byte."""
    entry = policy.get("entries", {}).get((observed["cik"], observed["accession"]))
    mismatch = (
        observed["cover_entry_total"] is not None
        and observed["cover_entry_total"] != observed["info_row_count"]
    ) or (
        observed["cover_value_total_raw_units"] is not None
        and observed["cover_value_total_raw_units"] != observed["info_value_sum_raw_units"]
    )
    if entry is not None:
        if any(entry[k] != observed[k] for k in IDENTITY_FIELDS + CONTROL_FIELDS):
            raise ValueError("approved quarantine source/control identity changed; review required")
        if not mismatch:
            raise ValueError("quarantine entry has no control contradiction; review required")
        return {**observed, **{k: policy[k] for k in
                ("policy_id", "policy_sha256", "methodology_version")}}
    if mismatch:
        raise ValueError("cover control totals do not match information table; unapproved source anomaly")
    return None
