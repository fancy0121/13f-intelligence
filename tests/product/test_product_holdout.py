"""Product holdout retrieval utility (Gate P6/P7/P5)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.tasks import build_task_universe, split_tasks


def _holdout_tasks(store):
    return split_tasks(build_task_universe(store, max_per_category=20, max_scan=2000))


def test_holdout_security_retrieval(store):
    tasks = [t for t in _holdout_tasks(store) if t["kind"] == "security" and t["part"] == "holdout"]
    assert len(tasks) >= 5
    for t in tasks[: min(len(tasks), 10)]:
        ev = store.security_evidence(t["key"])
        assert ev is not None
        # required fields present (retrieval utility)
        assert ev.cusip
        assert ev.resolution_status
        assert "holders" in ev.__dict__ or hasattr(ev, "holders")
        assert set(ev.activity_counts) == {"NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED"}
        assert ev.activity_state in (
            "MORE_ADDS_THAN_REDUCTIONS", "MORE_REDUCTIONS_THAN_ADDS", "MIXED_ACTIVITY",
            "NO_RECENT_CHANGE", "LOW_BREADTH", "STALE_DATA", "INSUFFICIENT_DATA",
        )


def test_holdout_manager_retrieval(store):
    tasks = [t for t in _holdout_tasks(store) if t["kind"] == "manager" and t["part"] == "holdout"]
    if not tasks:
        return
    for t in tasks[: min(len(tasks), 10)]:
        ev = store.manager_evidence(int(t["key"]))
        assert ev is not None
        assert ev.latest_changes is not None
        assert isinstance(ev.latest_changes.get("NEW"), list)


def test_quality_transparency_present(store):
    # unresolved/ambiguous security tasks must expose resolution_status
    tasks = [t for t in _holdout_tasks(store) if t["category"] == "security_unresolved_or_ambiguous"]
    if tasks:
        ev = store.security_evidence(tasks[0]["key"])
        assert ev.resolution_status not in ("VERIFIED_EXACT", "VERIFIED_MULTI_SOURCE", "VERIFIED_HISTORICAL")
        assert ev.quality["resolution_status"] == ev.resolution_status
