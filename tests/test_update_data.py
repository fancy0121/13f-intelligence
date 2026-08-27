"""Tests for scripts/update_data.py deployment-layer helpers."""

from __future__ import annotations

import importlib.util
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
