from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import connect, init_db, upsert_manager
from thirteenf.research.splits import (
    COMMON_WINDOW_END,
    COMMON_WINDOW_START,
    MANAGER_SPLIT_SEED,
    SECURITY_SPLIT_SEED,
    manager_split,
    protocol_time_split,
    security_split,
    time_split,
)


def test_time_split_chronological():
    periods = [
        "2023-09-30", "2023-12-31", "2024-03-31", "2024-06-30",
        "2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30",
        "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30",
    ]
    dev, hold = time_split(periods, dev_count=8)
    assert len(dev) == 8
    assert hold == ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
    assert set(dev) & set(hold) == set()


def test_time_split_insufficient():
    dev, hold = time_split(["2025-01-01", "2025-04-01"], dev_count=8)
    assert len(dev) == 2
    assert hold == []


def test_protocol_time_split_frozen_window():
    periods = [
        "2021-03-31", "2021-06-30", "2021-09-30", "2021-12-31",
        "2022-03-31", "2022-06-30", "2022-09-30", "2022-12-31",
        "2023-03-31", "2023-06-30",
        "2023-09-30", "2023-12-31", "2024-03-31", "2024-06-30",
        "2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30",
        "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30",
    ]
    dev, hold = protocol_time_split(periods)
    assert dev == [
        "2023-09-30", "2023-12-31", "2024-03-31", "2024-06-30",
        "2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30",
    ]
    assert hold == [
        "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30",
    ]
    assert COMMON_WINDOW_START == "2023-09-30"
    assert COMMON_WINDOW_END == "2026-06-30"


def test_manager_split_deterministic_and_seeded(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    for i in range(1, 30):
        upsert_manager(conn, name=f"M{i}", cik=1000 + i)
    a = manager_split(conn, seed=MANAGER_SPLIT_SEED)
    b = manager_split(conn, seed=MANAGER_SPLIT_SEED)
    assert a == b
    c = manager_split(conn, seed="different-seed")
    assert a != c
    conn.close()


def test_security_split_deterministic_and_seeded(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    from thirteenf.database import ensure_security

    for c in ("AAAA11111", "BBBB22222", "CCCC33333"):
        ensure_security(
            conn,
            cusip=c,
            ticker=None,
            issuer=None,
            share_class=None,
            mapping_status="UNRESOLVED",
            mapping_source="",
            mapping_date="2026-08-24",
        )
    a = security_split(conn, seed=SECURITY_SPLIT_SEED)
    b = security_split(conn, seed=SECURITY_SPLIT_SEED)
    assert a == b
    conn.close()
