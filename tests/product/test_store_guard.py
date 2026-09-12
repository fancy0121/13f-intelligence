"""Public-store snapshot and schema gate regressions."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "src"))

import store


def test_cold_start_does_not_enable_legacy_pages(monkeypatch):
    """A direct first request must execute the shared entrypoint and guards."""
    from streamlit.runtime.pages_manager import PagesManager

    monkeypatch.setattr(PagesManager, "uses_pages_directory", None)
    PagesManager(str(ROOT / "app" / "app.py"))

    assert PagesManager.uses_pages_directory is False


def test_old_database_is_not_validated_without_opening_product_store(tmp_path):
    db = tmp_path / "old.db"
    sqlite3.connect(db).close()

    error = store.database_validation_error(db)

    assert error is not None
    assert "NOT_VALIDATED" in error
    assert "effective_periods" in error


def test_app_stops_with_bilingual_not_validated_message_for_old_database(monkeypatch):
    pytest.importorskip("streamlit.testing")
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("THIRTEENF_DB_PATH", raising=False)
    at = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=30)
    at.run()

    assert not at.exception, at.exception
    assert any("数据库需重建" in str(error.value) and "NOT_VALIDATED" in str(error.value)
               for error in at.error)


def test_store_snapshot_key_changes_when_an_input_file_changes(tmp_path):
    paths = []
    for name in ("db", "resolution.csv", "semantic.csv", "managers.csv"):
        path = tmp_path / name
        path.write_text("one", encoding="utf-8")
        paths.append(path)

    before = store.store_snapshot_key(*paths, methodology_version="v1")
    paths[1].write_text("two-different-size", encoding="utf-8")
    after = store.store_snapshot_key(*paths, methodology_version="v1")

    assert before != after
    assert store.file_identity(paths[1]) in after


def test_cached_store_refreshes_after_resolution_snapshot_changes(tmp_path, monkeypatch):
    paths = []
    for name in ("db", "resolution.csv", "semantic.csv", "managers.csv"):
        path = tmp_path / name
        path.write_text("one", encoding="utf-8")
        paths.append(path)
    calls = []

    class FakeStore:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def quarantined_periods(self):
            return []

    monkeypatch.setattr(store, "ProductStore", FakeStore)
    monkeypatch.setenv("THIRTEENF_DB_PATH", str(paths[0]))
    monkeypatch.setenv("THIRTEENF_RESOLUTION_CSV", str(paths[1]))
    monkeypatch.setenv("THIRTEENF_SEMANTIC_CSV", str(paths[2]))
    monkeypatch.setenv("THIRTEENF_MANAGERS_CSV", str(paths[3]))
    store._get_store.clear()

    first = store.get_store()
    time.sleep(0.001)
    paths[1].write_text("changed", encoding="utf-8")
    second = store.get_store()

    assert first is not second
    assert len(calls) == 2


def test_first_local_read_copies_legacy_portfolio_to_private_path(tmp_path):
    legacy = tmp_path / "config" / "portfolio.csv"
    legacy.parent.mkdir()
    legacy.write_text("ticker,weight\nAAPL,0.25\n", encoding="utf-8")

    path, rows = store.load_local_portfolio(tmp_path)

    assert path == store.default_private_portfolio_path(tmp_path)
    assert rows == [{"ticker": "AAPL", "weight": "0.25"}]
    assert path.read_text(encoding="utf-8").endswith("AAPL,0.25\n")
    assert legacy.read_text(encoding="utf-8") == "ticker,weight\nAAPL,0.25\n"


@pytest.mark.parametrize("page", ["managers.py", "securities.py", "overview.py", "activity.py"])
def test_direct_data_page_fails_closed_without_public_traceback(tmp_path, monkeypatch, page):
    from streamlit.testing.v1 import AppTest
    db = tmp_path / "old-schema.db"
    sqlite3.connect(db).close()
    monkeypatch.setenv("THIRTEENF_DB_PATH", str(db))
    at = AppTest.from_file(str(ROOT / "app" / "views" / page), default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("NOT_VALIDATED" in str(error.value) for error in at.error)


def test_public_schema_v3_without_attestation_cannot_show_holdings(monkeypatch, tmp_path, product_bundle):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("THIRTEENF_PUBLIC_MODE", "1")
    monkeypatch.setenv("THIRTEENF_DB_PATH", str(product_bundle.db))
    monkeypatch.setenv("THIRTEENF_RELEASE_MANIFEST", str(tmp_path / "missing.json"))
    at = AppTest.from_file(str(ROOT / "app" / "views" / "securities.py"), default_timeout=30).run()
    assert not at.exception
    assert any("NOT_VALIDATED" in str(error.value) for error in at.error)
    assert not at.dataframe
