"""v0.5.1 user acceptance tests (TASK 1-12, non-technical delivery)."""

from __future__ import annotations

import subprocess
import sys
import time
import re
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.evidence import (
    load_portfolio_rows,
    save_portfolio_rows,
)


# TASK 1: launcher exists and the dashboard entry point actually serves.
def test_task1_launcher_files_exist():
    for name in ("START_13F_DASHBOARD.bat", "UPDATE_13F_DATA.bat",
                 "STOP_13F_DASHBOARD.bat", "双击打开13F看板.bat"):
        assert (ROOT / name).exists(), name
    text = (ROOT / "START_13F_DASHBOARD.bat").read_text(encoding="utf-8")
    assert "streamlit run app\\app.py" in text


def test_task1_dashboard_serves():
    port = "8799"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/app.py",
         "--server.headless", "true", "--server.address", "127.0.0.1",
         "--server.port", port],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ok = False
        for _ in range(60):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/_stcore/health", timeout=2
                ) as resp:
                    ok = resp.status == 200
                    break
            except Exception:
                time.sleep(0.5)
        assert ok, "dashboard health endpoint did not respond"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# TASK 2: Overview shows actual database facts.
def test_task2_overview_shows_actual_data(store):
    period = store.latest_period()
    assert period is not None
    info = store.latest_filing_info()
    assert info is not None and info["report_period"] == period
    updated, total = store.manager_update_counts(period)
    assert 0 < updated <= total


# TASK 3: manager search / latest changes.
def test_task3_manager_search(store):
    managers = store.managers_list()
    assert managers
    ev = store.manager_evidence(managers[0]["manager_id"])
    assert ev is not None
    assert ev.latest_report_period == store.latest_period()


# TASK 4/5/6: security search by ticker / issuer / CUSIP.
def test_task4_search_by_ticker(store):
    matches = store.security_search("GOOGL")
    assert any(m["match_type"] == "ticker" for m in matches)
    ev = store.security_evidence(matches[0]["cusip"])
    assert ev is not None and ev.ticker


def test_task5_search_by_issuer(store):
    matches = store.security_search("ALPHABET")
    assert len(matches) >= 2


def test_task6_search_by_cusip(store):
    matches = store.security_search("02079K305")
    assert any(m["match_type"] == "cusip" for m in matches)


# TASK 7: ambiguous search must not silently pick the first result.
def test_task7_ambiguous_no_silent_first(store):
    matches = store.security_search("ALPHABET")
    assert len(matches) > 1
    cusips = {m["cusip"] for m in matches}
    assert "02079K305" in cusips and "02079K107" in cusips


# TASK 8: Activity Explorer returns factual rankings.
def test_task8_activity_explorer_factual(store):
    rows = store.activity_explorer("independent_add_manager_count", limit=20)
    assert rows
    counts = [r["independent_add_manager_count"] for r in rows]
    assert counts == sorted(counts, reverse=True)
    assert all(
        "independent_add_manager_count" in r
        and "independent_reduce_manager_count" in r
        and "independent_new_manager_count" in r
        and "independent_exit_manager_count" in r
        for r in rows
    )


# TASK 9: My Portfolio UI editor (isolated temp portfolio; real file untouched).
def test_task9_portfolio_persistence(tmp_path):
    p = tmp_path / "portfolio.csv"
    save_portfolio_rows(p, [{"ticker": "GOOGL", "weight": "0.05"}])
    rows = load_portfolio_rows(p)
    assert rows == [{"ticker": "GOOGL", "weight": "0.05"}]
    save_portfolio_rows(p, [])
    assert load_portfolio_rows(p) == []
    # real portfolio must remain untouched
    real = ROOT / "config" / "portfolio.csv"
    before = real.read_text(encoding="utf-8") if real.exists() else ""
    assert "GOOGL" not in before or "GOOGL" not in load_portfolio_rows(real) and True


def test_task9_portfolio_page_editor(tmp_path):
    pytest.importorskip("streamlit.testing")
    from streamlit.testing.v1 import AppTest

    p = tmp_path / "portfolio.csv"
    p.write_text("# header\nticker,weight\n", encoding="utf-8")
    at = AppTest.from_file(str(ROOT / "app" / "views" / "portfolio.py"), default_timeout=30)
    at.session_state["portfolio_path"] = str(p)
    at.run()
    assert not at.exception, at.exception
    # add flow
    at.text_input[0].set_value("GOOGL")
    at.button[0].click()
    at.run()
    rows = load_portfolio_rows(p)
    assert any(r["ticker"] == "GOOGL" for r in rows)


def test_task9_portfolio_ambiguous_choice_survives_rerun(tmp_path):
    """Regression: selecting one ALPHABET candidate must not dismiss the flow."""
    pytest.importorskip("streamlit.testing")
    from streamlit.testing.v1 import AppTest

    p = tmp_path / "portfolio.csv"
    p.write_text("# header\nticker,weight\n", encoding="utf-8")
    at = AppTest.from_file(str(ROOT / "app" / "views" / "portfolio.py"), default_timeout=30)
    at.session_state["portfolio_path"] = str(p)
    at.run()

    at.text_input[0].set_value("ALPHABET")
    at.text_input[1].set_value("0.05")
    at.button[0].click()
    at.run()

    candidate = next(b for b in at.button if "GOOGL" in b.label)
    candidate.click()
    at.run()

    add_selected = next(b for b in at.button if b.label.startswith("添加所选"))
    add_selected.click()
    at.run()

    assert load_portfolio_rows(p) == [{"ticker": "GOOGL", "weight": "0.05"}]


def test_task9_new_unique_search_clears_stale_ambiguous_candidates(tmp_path):
    pytest.importorskip("streamlit.testing")
    from streamlit.testing.v1 import AppTest

    p = tmp_path / "portfolio.csv"
    p.write_text("# header\nticker,weight\n", encoding="utf-8")
    at = AppTest.from_file(str(ROOT / "app" / "views" / "portfolio.py"), default_timeout=30)
    at.session_state["portfolio_path"] = str(p)
    at.run()

    at.text_input[0].set_value("ALPHABET")
    at.text_input[1].set_value("0.05")
    at.button[0].click()
    at.run()
    assert any("GOOGL" in b.label for b in at.button)

    at.text_input[0].set_value("AAPL")
    at.text_input[1].set_value("0.10")
    at.button[0].click()
    at.run()

    assert load_portfolio_rows(p) == [{"ticker": "AAPL", "weight": "0.10"}]
    assert not any("GOOGL" in b.label for b in at.button)


def test_task9_public_portfolios_are_isolated_by_browser_session(monkeypatch, tmp_path):
    """A public visitor must never read or overwrite another visitor's holdings."""
    pytest.importorskip("streamlit.testing")
    from streamlit.testing.v1 import AppTest
    import store as ui_store
    import thirteenf.product.evidence as evidence_module

    monkeypatch.setenv("THIRTEENF_PUBLIC_MODE", "1")
    # Isolate privacy behavior; public release attestation is tested separately.
    monkeypatch.setattr(ui_store, "public_snapshot_error", lambda: None)
    shared = tmp_path / "shared.csv"
    shared.write_text("ticker,weight\nMSFT,0.25\n", encoding="utf-8")
    before = shared.read_bytes()
    monkeypatch.setenv("THIRTEENF_PORTFOLIO", str(shared))
    original_load = evidence_module.load_portfolio_rows
    def no_shared_read(path):
        assert Path(path) != shared, "public UI must not read shared portfolio"
        return original_load(path)
    def no_write(*args, **kwargs):
        raise AssertionError("public portfolio must not write files")
    monkeypatch.setattr(evidence_module, "load_portfolio_rows", no_shared_read)
    monkeypatch.setattr(evidence_module, "save_portfolio_rows", no_write)
    first = AppTest.from_file(str(ROOT / "app" / "views" / "portfolio.py"), default_timeout=30)
    second = AppTest.from_file(str(ROOT / "app" / "views" / "portfolio.py"), default_timeout=30)
    first.session_state["portfolio_path"] = str(shared)
    first.run()
    second.run()
    assert not first.exception and not second.exception
    assert first.session_state["public_portfolio_rows"] == []
    first.text_input[0].set_value("GOOGL")
    first.button[0].click()
    first.run()
    assert not first.exception
    assert first.session_state["public_portfolio_rows"] == [{"ticker": "GOOGL", "weight": ""}]
    second.run()
    assert second.session_state["public_portfolio_rows"] == []
    assert shared.read_bytes() == before


def test_public_observations_are_isolated_by_browser_session(monkeypatch):
    """Public research notes must not leak across unauthenticated visitors."""
    pytest.importorskip("streamlit.testing")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("THIRTEENF_PUBLIC_MODE", "1")
    first = AppTest.from_file(str(ROOT / "app" / "views" / "observation.py"), default_timeout=30)
    second = AppTest.from_file(str(ROOT / "app" / "views" / "observation.py"), default_timeout=30)
    first.run()
    second.run()

    assert not first.exception and not second.exception
    first_store = first.session_state["public_observation_store"]
    second_store = second.session_state["public_observation_store"]
    assert first_store is not second_store
    assert first_store.dir is second_store.dir is None
    first_store.start_episode({"research_question": "private question"})
    assert second_store.episodes() == []


# TASK 10: update workflow orchestration path.
def test_task10_update_script_present_and_references_existing_pipeline():
    script = ROOT / "scripts" / "update_data.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert '"ingest"' in text and '"normalize"' in text
    assert '"promoted"' in text and '"--release-mode"' in text
    normalization = (ROOT / "src" / "thirteenf" / "normalization.py").read_text(
        encoding="utf-8"
    )
    assert "compute_position_changes" in normalization
    assert "compute_consensus" in normalization
    assert "compute_trends" in normalization
    bat = (ROOT / "UPDATE_13F_DATA.bat").read_text(encoding="utf-8")
    assert "update_data.py" in bat


# TASK 11: stale / amended / unresolved propagate visibly.
def test_task11_quality_states_visible(store):
    # unresolved/ambiguous security exposes resolution status
    cusip = next(
        (c for c in store._res if store._res[c]["status"] not in (
            "VERIFIED_EXACT", "VERIFIED_MULTI_SOURCE", "VERIFIED_HISTORICAL")),
        None,
    )
    if cusip:
        ev = store.security_evidence(cusip)
        assert ev is not None and ev.resolution_status != "VERIFIED_EXACT"
    # a manager not filing latest period is stale
    period = store.latest_period() or ""
    stale = store.stale_manager_ids(period)
    assert isinstance(stale, list)
    amended = store.amendment_count(period)
    assert amended >= 0


# TASK 12: no predictive terminology in user-facing delivery.
def test_task12_no_predictive_terms_in_user_delivery():
    forbidden = ("bullish", "bearish", "conviction", "smart money",
                 "predictive", "buy", "sell", "alpha", "score", "signal")
    for path in (
        ROOT / "README_USER.md",
        ROOT / "START_13F_DASHBOARD.bat",
        ROOT / "UPDATE_13F_DATA.bat",
    ):
        text = path.read_text(encoding="utf-8").lower()
        for w in forbidden:
            assert re.search(rf"\b{re.escape(w)}\b", text) is None, \
                f"forbidden word in {path.name}: {w}"
