"""Product task manifest determinism (Gate P6)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.tasks import _hash_part, build_task_universe, split_tasks, write_manifest


def test_hash_split_deterministic():
    assert _hash_part("security:02079K305") == _hash_part("security:02079K305")
    parts = {_hash_part(f"security:{i}") for i in range(200)}
    assert "development" in parts and "holdout" in parts


def test_task_universe_categories(store):
    tasks = build_task_universe(store, max_per_category=40, max_scan=2000)
    cats = {t["category"] for t in tasks}
    assert "security_high_breadth" in cats
    assert "manager_current" in cats
    assert any(t["kind"] == "security" for t in tasks)
    assert any(t["kind"] == "manager" for t in tasks)


def test_split_manifest_reproducible(store, tmp_path):
    tasks = build_task_universe(store, max_per_category=40, max_scan=2000)
    split1 = split_tasks(tasks)
    split2 = split_tasks(tasks)
    assert split1 == split2
    p = tmp_path / "manifest.csv"
    write_manifest(split1, p)
    from thirteenf.product.tasks import load_manifest

    df = load_manifest(p)
    assert len(df) == len(split1)
    assert set(df["part"]) <= {"development", "holdout"}


def test_holdout_tasks_exist(store, tmp_path):
    tasks = split_tasks(build_task_universe(store, max_per_category=40, max_scan=2000))
    holdout = [t for t in tasks if t["part"] == "holdout"]
    dev = [t for t in tasks if t["part"] == "development"]
    assert len(dev) > 0
    assert len(holdout) > 0
