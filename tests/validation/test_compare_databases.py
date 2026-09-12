from __future__ import annotations

import shutil
import sqlite3

from thirteenf.validation.compare_databases import compare_databases


def test_semantic_database_comparison_detects_change(sample_bundle, tmp_path):
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    shutil.copy2(sample_bundle.db_path, first)
    shutil.copy2(sample_bundle.db_path, second)
    assert compare_databases(first, second).matches
    conn = sqlite3.connect(second)
    conn.execute("UPDATE effective_positions SET value=value+1 WHERE effective_position_id=1")
    conn.commit()
    conn.close()
    result = compare_databases(first, second)
    assert not result.matches
    assert "effective_positions" in result.different_tables


def test_semantic_database_comparison_ignores_documented_timestamps(
    sample_bundle, tmp_path
):
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    shutil.copy2(sample_bundle.db_path, first)
    shutil.copy2(sample_bundle.db_path, second)
    conn = sqlite3.connect(second)
    conn.execute(
        "UPDATE schema_version SET applied_at_utc='2099-01-01T00:00:00Z'"
    )
    conn.execute(
        "UPDATE quality_events SET created_at_utc='2099-01-01T00:00:00Z'"
    )
    conn.commit()
    conn.close()
    assert compare_databases(first, second).matches
