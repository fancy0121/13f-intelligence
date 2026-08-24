"""Security Resolution tests (protocol v0.2.1). No network."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.research.resolution.coverage import (
    compute_coverage,
    gate_evaluation,
    persistence_observations,
)
from thirteenf.research.resolution.engine import is_verified_status, resolve_cusip
from thirteenf.research.resolution.history import load_historical_symbols
from thirteenf.research.resolution.models import (
    HistoricalSymbol,
    OpenFIGIRecord,
    OpenFIGIResponse,
    ResolutionStatus,
)
from thirteenf.research.resolution.sources import (
    SECIndex,
    canonical_norm,
    distinct_us_tickers,
    names_match,
    parse_openfigi_entry,
    raw_norm,
    us_filter,
)


def rec(ticker="AMZN", exch="US", sec_type="Common Stock", sector="Equity", name="AMAZON.COM INC", scf="BBG001S5PQL7"):
    return OpenFIGIRecord(
        figi="BBG000BVPV84",
        compositeFIGI="BBG000BVPV84",
        shareClassFIGI=scf,
        ticker=ticker,
        exchCode=exch,
        securityType=sec_type,
        marketSector=sector,
        name=name,
        securityDescription=ticker,
    )


def response(*records, error=None):
    return OpenFIGIResponse(
        id_type="ID_CUSIP", id_value="X", records=tuple(records), error=error
    )


SEC_RECORDS = [
    {"cik": "1018724", "ticker": "AMZN", "title": "AMAZON COM INC", "exchange": ""},
    {"cik": "1652044", "ticker": "GOOGL", "title": "Alphabet Inc.", "exchange": ""},
    {"cik": "1652044", "ticker": "GOOG", "title": "Alphabet Inc.", "exchange": ""},
    {"cik": "1652044", "ticker": "GOOGM", "title": "Alphabet Inc.", "exchange": ""},
    {"cik": "1326801", "ticker": "META", "title": "Meta Platforms, Inc.", "exchange": ""},
    {"cik": "789019", "ticker": "MSFT", "title": "MICROSOFT CORP", "exchange": ""},
    {"cik": "1046179", "ticker": "TSM", "title": "TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD", "exchange": ""},
    {"cik": "1046179", "ticker": "TSMWF", "title": "TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD", "exchange": ""},
    {"cik": "1512673", "ticker": "XYZ", "title": "Block, Inc.", "exchange": ""},
    {"cik": "1737806", "ticker": "PDD", "title": "PDD Holdings Inc.", "exchange": ""},
    {"cik": "1045810", "ticker": "NVDA", "title": "NVIDIA CORP", "exchange": ""},
    {"cik": "927628", "ticker": "COF", "title": "CAPITAL ONE FINANCIAL CORP", "exchange": ""},
    {"cik": "1792789", "ticker": "DASH", "title": "DoorDash, Inc.", "exchange": ""},
]


def test_openfigi_parse_unique_and_error():
    entry = {"data": [{"figi": "F", "ticker": "AMZN", "exchCode": "US", "name": "X"}]}
    r = parse_openfigi_entry(entry, "ID_CUSIP", "023135106")
    assert r.id_type == "ID_CUSIP"
    assert len(r.records) == 1
    assert r.records[0].ticker == "AMZN"
    err = parse_openfigi_entry({"error": "Invalid idType"}, "ID_CUSIP", "X")
    assert err.error
    assert err.records == ()


def test_us_filter_and_distinct_tickers_googl_tsm_block_pdd():
    googl = response(
        rec("GOOGL", "US", name="ALPHABET INC-CL A", scf="BBG009S39JY5"),
        rec("GOOGL", "UN", name="ALPHABET INC-CL A", scf="BBG009S39JY5"),
        rec("ABEA", "GR", name="ALPHABET INC-CL A", scf="BBG009S39JY5"),
        rec("1GOOGL", "IM", name="ALPHABET INC-CL A", scf="BBG009S39JY5"),
    )
    assert distinct_us_tickers(googl.records) == ["GOOGL"]
    assert len(us_filter(googl.records)) == 2

    tsm = response(rec("TSM", "US", sec_type="ADR", name="TAIWAN SEMICONDUCTOR-SP ADR", scf="BBG001S5WWW4"))
    assert distinct_us_tickers(tsm.records) == ["TSM"]
    block = response(rec("XYZ", "US", name="BLOCK INC", scf="BBG001TFLWL5"))
    assert distinct_us_tickers(block.records) == ["XYZ"]
    pdd = response(rec("PDD", "US", sec_type="ADR", name="PDD HOLDINGS INC", scf="BBG00LBLDFH8"))
    assert distinct_us_tickers(pdd.records) == ["PDD"]


def test_rule_c_verified_exact():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "023135106", "AMAZON COM INC", "COM", response(rec()), sec, {}
    )
    assert res.status == ResolutionStatus.VERIFIED_MULTI_SOURCE.value
    assert res.records[0].symbol == "AMZN"
    assert is_verified_status(res.status)


def test_rule_c_without_sec_unique_ticker_is_verified_exact():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "02079K305", "ALPHABET INC", "CL A",
        response(rec("GOOGL", "US", name="ALPHABET INC-CL A", scf="BBG009S39JY5")),
        sec, {},
    )
    assert res.status == ResolutionStatus.VERIFIED_EXACT.value  # SEC has 4 tickers
    assert res.records[0].symbol == "GOOGL"


def test_share_class_goog_vs_googl_not_merged():
    sec = SECIndex(SEC_RECORDS)
    r_a = resolve_cusip(
        "02079K305", "ALPHABET INC", "CL A",
        response(rec("GOOGL", "US", name="ALPHABET INC-CL A", scf="BBG009S39JY5")),
        sec, {},
    )
    r_c = resolve_cusip(
        "02079K107", "ALPHABET INC", "CL C",
        response(rec("GOOG", "US", name="ALPHABET INC-CL C", scf="BBG009S3NB21")),
        sec, {},
    )
    assert r_a.records[0].symbol == "GOOGL"
    assert r_c.records[0].symbol == "GOOG"
    assert r_a.records[0].symbol != r_c.records[0].symbol


def test_rule_b_sec_only_when_openfigi_empty():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip("999999999", "NVIDIA CORP", "", response(), sec, {})
    assert res.status == ResolutionStatus.VERIFIED_EXACT.value
    assert res.records[0].symbol == "NVDA"
    assert res.sources == ["sec"]


def test_ambiguous_multiple_us_tickers():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "X", "ACME CORP", "",
        response(rec("AAA", "US"), rec("BBB", "US")), sec, {},
    )
    assert res.status == ResolutionStatus.AMBIGUOUS.value
    assert not is_verified_status(res.status)


def test_conflict_sec_unique_differs():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "X", "MICROSOFT CORP", "",
        response(rec("MSFT", "US", name="MICROSOFT CORP")),
        SECIndex([{"cik": "1", "ticker": "ZZZ", "title": "MICROSOFT CORP", "exchange": ""}]),
        {},
    )
    assert res.status == ResolutionStatus.CONFLICT.value


def test_unresolved_no_corroboration_no_silent_fallback():
    sec = SECIndex([])
    res = resolve_cusip(
        "722304102", "SOME UNKNOWN ISSUER", "",
        response(rec("PDD", "US", sec_type="ADR", name="PDD HOLDINGS INC")),
        sec, {},
    )
    assert res.status == ResolutionStatus.UNRESOLVED.value
    assert not is_verified_status(res.status)


def test_unresolved_when_openfigi_and_sec_empty():
    sec = SECIndex([])
    res = resolve_cusip("722304102", "SOME UNKNOWN ISSUER", "", response(), sec, {})
    assert res.status == ResolutionStatus.UNRESOLVED.value


def test_non_equity_rejected():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "X", "SOME FUND", "",
        response(rec("FUND", "US", sec_type="Closed-End Fund", sector="Fund")),
        sec, {},
    )
    assert res.status == ResolutionStatus.NON_EQUITY_OR_UNSUPPORTED.value


def test_foreign_only_no_us_venue():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "X", "ACME", "",
        response(rec("ACME", "GR", name="ACME CORP")), sec, {},
    )
    assert res.status == ResolutionStatus.UNRESOLVED.value
    assert "no US venue record" in res.notes[0]


def test_adr_mismatch_conflict():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "X", "SOME CO", "SP ADR",
        response(rec("AAA", "US", sec_type="Common Stock", name="SOME CO")), sec, {},
    )
    assert res.status == ResolutionStatus.CONFLICT.value


def test_historical_symbol_makes_verified_historical():
    sec = SECIndex(SEC_RECORDS)
    hist = {
        "852234103": [
            HistoricalSymbol("852234103", "SQ", "2015-11-19", "2026-01-07", "curated-test")
        ]
    }
    res = resolve_cusip(
        "852234103", "BLOCK INC", "COM",
        response(rec("XYZ", "US", name="BLOCK INC", scf="BBG001TFLWL5")), sec, hist,
    )
    assert res.status == ResolutionStatus.VERIFIED_HISTORICAL.value
    symbols = [r.symbol for r in res.records]
    assert "XYZ" in symbols and "SQ" in symbols
    assert is_verified_status(res.status)


def test_negative_first_result_wins_rejected():
    # Multiple records, first is foreign: must NOT pick the first.
    resp = response(
        rec("AMZ", "GR", name="AMAZON.COM INC"),
        rec("AMZN", "US", name="AMAZON.COM INC"),
    )
    assert distinct_us_tickers(resp.records) == ["AMZN"]
    assert us_filter(resp.records)[0].ticker == "AMZN"


def test_negative_yahoo_search_not_used():
    import inspect
    import thirteenf.research.resolution.engine as engine
    src = inspect.getsource(engine)
    assert "yahoo" not in src.lower() or "search" not in src.lower()
    sig = inspect.signature(engine.resolve_cusip)
    assert "future" not in sig.parameters
    assert "return" not in sig.parameters
    assert "outcome" not in sig.parameters


def test_negative_no_fact_mutation():
    # resolve_cusip returns dataclasses; it must not import database writes.
    import inspect
    import thirteenf.research.resolution.engine as engine
    assert "sqlite3" not in inspect.getsource(engine)


def test_names_match_and_normalization():
    assert names_match("NVIDIA CORPORATION", "NVIDIA CORP")
    assert names_match("AMAZON.COM INC", "AMAZON COM INC")
    assert names_match("ALPHABET INC", "ALPHABET INC-CL A")
    assert names_match("CAPITAL ONE FINL CORP", "CAPITAL ONE FINANCIAL CORP")
    assert not names_match("APPLE INC", "BANANA CORP")
    assert raw_norm("  APPLE , Inc. ") == "APPLE INC"
    assert canonical_norm("NVIDIA CORP") == canonical_norm("NVIDIA CORPORATION")


def test_sec_index_abbreviation_and_ambiguity():
    sec = SECIndex(SEC_RECORDS)
    assert sec.unique_ticker("NVIDIA CORPORATION") == "NVDA"
    assert sec.unique_ticker("ALPHABET INC") is None  # multiple classes
    assert sec.unique_ticker("CAPITAL ONE FINL CORP") == "COF"
    assert sec.corroborates("MICROSOFT CORP", "MICROSOFT CORP")


def test_tsm_adr_corroborated_via_sec_issuer_ticker_set():
    sec = SECIndex(SEC_RECORDS)
    res = resolve_cusip(
        "874039100", "TAIWAN SEMICONDUCTOR MANUFAC", "SPONSORED ADS",
        response(rec("TSM", "US", sec_type="ADR", name="TAIWAN SEMICONDUCTOR-SP ADR", scf="BBG001S5WWW4")),
        sec, {},
    )
    assert res.status == ResolutionStatus.VERIFIED_EXACT.value
    assert res.records[0].symbol == "TSM"
    assert "sec_ticker_file" in res.sources


def test_etf_corroborated_via_sec_title_lookup():
    # SEC title (full fund name) matches OpenFIGI name; ticker agrees.
    sec = SECIndex(
        [
            {"cik": "1", "ticker": "WTAI", "title": "WISDOMTREE ARTIFICIAL INTELLIGENCE AND INNOVATION FUND", "exchange": ""},
            {"cik": "1", "ticker": "WTAI", "title": "WISDOMTREE ARTIFICIAL INTELLIGENCE AND INNOVATION FUND", "exchange": ""},
        ]
    )
    res = resolve_cusip(
        "97717Y543", "WISDOMTREE TR", "ARTIFICIAL INTEL",
        response(rec("WTAI", "US", sec_type="ETP", name="WISDOMTREE ARTIFICIAL INTELLIGENCE AND INNOVATION FUND")),
        sec, {},
    )
    assert res.status == ResolutionStatus.VERIFIED_MULTI_SOURCE.value
    assert res.records[0].symbol == "WTAI"


def test_etf_conflict_when_unique_sec_title_ticker_differs():
    sec = SECIndex(
        [{"cik": "1", "ticker": "OTHER", "title": "SOME FUND NAME", "exchange": ""}]
    )
    res = resolve_cusip(
        "X", "SOME TRUST", "SOME FUND",
        response(rec("AAA", "US", sec_type="ETP", name="SOME FUND NAME")),
        sec, {},
    )
    assert res.status == ResolutionStatus.CONFLICT.value


def test_openfigi_client_cache_and_batch(tmp_path):
    import json
    from thirteenf.research.resolution.sources import OpenFIGIClient

    calls = {"n": 0}

    def transport(payload):
        calls["n"] += 1
        jobs = json.loads(payload)
        return 200, json.dumps(
            [{"data": [{"ticker": f"T{i}", "exchCode": "US"}]} for i in range(len(jobs))]
        ).encode("utf-8")

    client = OpenFIGIClient(tmp_path / "ofcache", transport=transport, sleep_s=0)
    jobs = [{"idType": "ID_CUSIP", "idValue": f"C{i:03d}"} for i in range(25)]
    res = client.mapping(jobs)
    assert len(res) == 25
    # 25 jobs -> 3 batches of <=10
    assert calls["n"] == 3
    res2 = client.mapping(jobs)
    assert calls["n"] == 3  # cache hit, no extra calls
    assert res2[0].records[0].ticker == "T0"


def test_openfigi_client_retry_on_429(tmp_path):
    from thirteenf.research.resolution.sources import OpenFIGIClient

    attempts = {"n": 0}

    def transport(payload):
        attempts["n"] += 1
        if attempts["n"] < 2:
            return 429, b""
        return 200, b'[{"data":[{"ticker":"T","exchCode":"US"}]}]'

    client = OpenFIGIClient(tmp_path / "ofretry", transport=transport, sleep_s=0, max_retries=2)
    res = client.mapping([{"idType": "ID_CUSIP", "idValue": "C"}])
    assert res[0].records[0].ticker == "T"
    assert attempts["n"] == 2


def test_historical_csv_loader(tmp_path):
    p = tmp_path / "h.csv"
    p.write_text(
        "# comment\ncusip,symbol,valid_from,valid_to,source,notes\n"
        "852234103,SQ,2015-11-19,2026-01-07,curated,\n",
        encoding="utf-8",
    )
    m = load_historical_symbols(p)
    assert m["852234103"][0].symbol == "SQ"
    assert load_historical_symbols(tmp_path / "missing.csv") == {}


def test_persistence_observations():
    df = pd.DataFrame(
        {
            "manager_id": [1, 1, 1, 2, 2, 2],
            "security_id": [10, 10, 10, 20, 20, 20],
            "cusip": ["A", "A", "A", "B", "B", "B"],
            "report_period": ["2024-01-01", "2024-04-01", "2024-07-01"] * 2,
            "change_type": ["ADD", "ADD", "ADD", "ADD", "REDUCE", "ADD"],
        }
    )
    out = persistence_observations(df, 2)
    assert len(out) == 2  # only manager 1 rows persist (2+ consecutive ADD)
    assert set(out["security_id"]) == {10}


def test_coverage_gates_mechanical():
    frames = {
        "O0": pd.DataFrame(
            {
                "cusip": ["A"] * 10 + ["B"] * 10,
                "info_date": ["2024-01-01"] * 20,
                "part": ["H0_dev"] * 8 + ["H1_time_holdout"] * 12,
                "activity": ["positive"] * 10 + ["negative"] * 10,
                "change_type": ["ADD"] * 10 + ["REDUCE"] * 10,
            }
        ),
        "O1_2Q": pd.DataFrame(
            {
                "cusip": ["A"] * 10,
                "info_date": ["2024-01-01"] * 10,
                "part": ["H0_dev"] * 10,
                "activity": ["positive"] * 10,
                "change_type": ["ADD"] * 10,
            }
        ),
        "O1_3Q": pd.DataFrame(
            {
                "cusip": ["A"] * 10,
                "info_date": ["2024-01-01"] * 10,
                "part": ["H0_dev"] * 10,
                "activity": ["positive"] * 10,
                "change_type": ["ADD"] * 10,
            }
        ),
    }
    master = pd.DataFrame(
        [
            {"cusip": "A", "status": "VERIFIED_EXACT", "symbol": "AAA"},
            {"cusip": "B", "status": "UNRESOLVED", "symbol": ""},
        ]
    )
    avail = pd.DataFrame([{"symbol": "AAA", "first_trade_date": "2020-01-01"}])
    cov = compute_coverage(frames, master, avail)
    assert cov["O0"]["observation_coverage"] == 50.0
    assert cov["O1_2Q"]["observation_coverage"] == 100.0
    gates = gate_evaluation(cov)
    assert gates["O0"]["overall_gate"] is False
    assert gates["O1_2Q"]["PASS"] is True
    # info date before availability start -> not covered
    frames2 = {
        k: pd.DataFrame(
            {
                "cusip": ["A"] * 5,
                "info_date": ["2019-01-01"] * 5,
                "part": ["H0_dev"] * 5,
                "activity": ["positive"] * 5,
                "change_type": ["ADD"] * 5,
            }
        )
        for k in ("O0", "O1_2Q", "O1_3Q")
    }
    cov2 = compute_coverage(frames2, master, avail)
    assert cov2["O0"]["observation_coverage"] == 0.0


def test_gate_variant_bias_flag():
    # O1/O2 much higher than O0 => VARIANT_MAPPING_BIAS
    frames = {
        "O0": pd.DataFrame(
            {
                "cusip": ["A", "B", "C", "D"],
                "info_date": ["2024-01-01"] * 4,
                "part": ["H0_dev"] * 4,
                "activity": ["positive"] * 4,
                "change_type": ["ADD"] * 4,
            }
        ),
        "O1_2Q": pd.DataFrame(
            {
                "cusip": ["A", "B"],
                "info_date": ["2024-01-01"] * 2,
                "part": ["H0_dev"] * 2,
                "activity": ["positive"] * 2,
                "change_type": ["ADD"] * 2,
            }
        ),
        "O1_3Q": pd.DataFrame(
            {
                "cusip": ["A"],
                "info_date": ["2024-01-01"],
                "part": ["H0_dev"],
                "activity": ["positive"],
                "change_type": ["ADD"],
            }
        ),
    }
    master = pd.DataFrame(
        [
            {"cusip": "A", "status": "VERIFIED_EXACT", "symbol": "AAA"},
            {"cusip": "B", "status": "UNRESOLVED", "symbol": ""},
            {"cusip": "C", "status": "UNRESOLVED", "symbol": ""},
            {"cusip": "D", "status": "UNRESOLVED", "symbol": ""},
        ]
    )
    avail = pd.DataFrame([{"symbol": "AAA", "first_trade_date": "2020-01-01"}])
    cov = compute_coverage(frames, master, avail)
    gates = gate_evaluation(cov)
    assert gates["variant_differential_bias"]["VARIANT_MAPPING_BIAS"] is True
