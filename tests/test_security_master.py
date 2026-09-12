from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.security_master import SecurityMapping, load_mappings, resolve


def _write_csv(tmp_path, content: str) -> Path:
    p = tmp_path / "mappings.csv"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_and_resolve_verified(tmp_path):
    p = _write_csv(
        tmp_path,
        (
            "cusip,ticker,issuer,share_class,mapping_status,mapping_source,"
            "verified_at,verified_by,notes\n"
            "037833100,AAPL,Apple Inc.,COM,VERIFIED,MANUAL_REVIEW,"
            "2026-08-24,TEST_REVIEWER,\n"
        ),
    )
    mappings = load_mappings(p)
    assert mappings["037833100"].ticker == "AAPL"
    m = resolve(mappings, "037833100")
    assert m.mapping_status == "VERIFIED"
    assert m.ticker == "AAPL"


def test_unresolved_when_missing(tmp_path):
    p = _write_csv(
        tmp_path,
        (
            "cusip,ticker,issuer,share_class,mapping_status,mapping_source,"
            "verified_at,verified_by,notes\n"
            "037833100,AAPL,Apple Inc.,COM,VERIFIED,MANUAL_REVIEW,"
            "2026-08-24,TEST_REVIEWER,\n"
        ),
    )
    m = resolve(load_mappings(p), "999999999")
    assert m.mapping_status == "UNRESOLVED"
    assert m.ticker is None


def test_goog_googl_share_classes_not_merged(tmp_path):
    p = _write_csv(
        tmp_path,
        (
            "cusip,ticker,issuer,share_class,mapping_status,mapping_source,"
            "verified_at,verified_by,notes\n"
            "02079K305,GOOGL,Alphabet Inc.,CL A,VERIFIED,MANUAL_REVIEW,"
            "2026-08-24,TEST_REVIEWER,\n"
            "02079K107,GOOG,Alphabet Inc.,CL C,VERIFIED,MANUAL_REVIEW,"
            "2026-08-24,TEST_REVIEWER,\n"
        ),
    )
    mappings = load_mappings(p)
    assert mappings["02079K305"].ticker == "GOOGL"
    assert mappings["02079K107"].ticker == "GOOG"


def test_missing_mapping_file_returns_empty():
    assert load_mappings(Path("does_not_exist.csv")) == {}


@pytest.mark.parametrize("status", ["UNRESOLVED", "CONFLICT", "RETIRED"])
def test_unverified_status_never_exposes_ticker(tmp_path, status):
    p = _write_csv(tmp_path, "cusip,ticker,mapping_status\n037833100,AAPL," + status + "\n")
    assert resolve(load_mappings(p), "037833100").ticker is None


def test_verified_without_provenance_fails_closed(tmp_path):
    p = _write_csv(tmp_path, "cusip,ticker,mapping_status\n037833100,AAPL,VERIFIED\n")
    with pytest.raises(ValueError, match="provenance"):
        load_mappings(p)


def test_conflicting_duplicate_cusip_is_not_silently_overwritten(tmp_path):
    p = _write_csv(tmp_path, "cusip,ticker,mapping_status\n037833100,AAPL,CONFLICT\n037833100,XYZ,RETIRED\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_mappings(p)
