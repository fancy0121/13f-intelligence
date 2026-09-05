"""Tests for scripts/update_data.py deployment-layer helpers."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_data.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("update_data", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["update_data"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def update_data():
    return _load_module()


def test_parse_int_separate_lines(update_data):
    out = "verified_managers=29\nraw_files=333\nfailures=6\n"
    assert update_data._parse_int(out, "verified_managers") == 29
    assert update_data._parse_int(out, "raw_files") == 333
    assert update_data._parse_int(out, "failures") == 6


def test_parse_int_same_line(update_data):
    # cli.py prints "raw_files=333 failures=6" on ONE line; the parser must
    # still find both keys (regression: failures was parsed as None -> crash).
    out = "raw_files=333 failures=6\n"
    assert update_data._parse_int(out, "raw_files") == 333
    assert update_data._parse_int(out, "failures") == 6


def test_parse_int_missing_and_invalid(update_data):
    assert update_data._parse_int("no stats here\n", "failures") is None
    assert update_data._parse_int("raw_files=333 failures=abc\n", "failures") is None


def _prepare_update_paths(update_data, monkeypatch, tmp_path):
    db_path = tmp_path / "thirteenf.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE filings(filing_id INTEGER);"
        "CREATE TABLE holdings(holding_id INTEGER);"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(update_data, "DB", db_path)
    monkeypatch.setattr(update_data, "STATUS_PATH", tmp_path / "last_update.json")
    monkeypatch.setattr(update_data, "LOG_PATH", tmp_path / "last_update.log")


def test_rate_limit_rps_flag_is_forwarded(update_data, monkeypatch, tmp_path):
    _prepare_update_paths(update_data, monkeypatch, tmp_path)
    calls = []

    def fake_run(step, args):
        calls.append((step, args))
        if step == "ingest":
            return 0, "raw_files=1 failures=0"
        return 0, "processed=1 failed=0 pending_amendments=0 promoted=1"

    monkeypatch.setattr(update_data, "_run", fake_run)
    assert update_data.main(["--rate-limit-rps", "2.5"]) == 0
    ingest_args = next(args for step, args in calls if step == "ingest")
    assert ingest_args[-2:] == ["--rate-limit-rps", "2.5"]


def test_absent_rate_flag_does_not_mask_environment(
    update_data, monkeypatch, tmp_path
):
    _prepare_update_paths(update_data, monkeypatch, tmp_path)
    calls = []

    def fake_run(step, args):
        calls.append((step, args))
        if step == "ingest":
            return 0, "raw_files=1 failures=0"
        return 0, "processed=1 failed=0 pending_amendments=0 promoted=1"

    monkeypatch.setattr(update_data, "_run", fake_run)
    assert update_data.main([]) == 0
    ingest_args = next(args for step, args in calls if step == "ingest")
    assert "--rate-limit-rps" not in ingest_args
    assert "--rate-limit-s" not in ingest_args


def test_changed_filing_failure_blocks_release(update_data, monkeypatch, tmp_path):
    _prepare_update_paths(update_data, monkeypatch, tmp_path)
    calls = []

    def fake_run(step, args):
        calls.append((step, args))
        return 1, "raw_files=2 failures=1 changed_failures=1"

    monkeypatch.setattr(update_data, "_run", fake_run)
    assert update_data.main(["--release-mode"]) == 1
    assert [step for step, _ in calls] == ["ingest"]
    status = json.loads(update_data.STATUS_PATH.read_text(encoding="utf-8"))
    assert status["releaseable"] is False


def test_normalize_only_forwards_raw_root_and_database(
    update_data, monkeypatch, tmp_path
):
    _prepare_update_paths(update_data, monkeypatch, tmp_path)
    raw_root = tmp_path / "raw"
    calls = []

    def fake_run(step, args):
        calls.append((step, args))
        return 0, "processed=1 failed=0 pending_amendments=0 promoted=1"

    monkeypatch.setattr(update_data, "_run", fake_run)
    assert update_data.main(
        ["--normalize-only", "--raw-root", str(raw_root), "--db", str(update_data.DB)]
    ) == 0
    assert [step for step, _ in calls] == ["normalize"]
    normalize_args = calls[0][1]
    assert normalize_args[normalize_args.index("--raw-root") + 1] == str(raw_root)
    assert normalize_args[normalize_args.index("--db-path") + 1] == str(update_data.DB)
