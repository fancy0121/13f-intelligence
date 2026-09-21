from __future__ import annotations

import json
import sys
import pytest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.filings import (
    FilingRecord,
    dedupe_effective,
    discover_filings,
    latest_n_quarters,
    parse_submissions,
)


def _record(report_date: str, accession: str, form: str = "13F-HR") -> FilingRecord:
    return FilingRecord(
        cik=1,
        accession_number=accession,
        form_type=form,
        filing_date="2026-08-14",
        report_date=report_date,
        primary_document="InfoTable.xml",
    )


def test_parse_submissions_filters_13f_only():
    payload = {
        "filings": {
            "recent": {
                "form": ["13F-HR", "4", "13F-HR/A", "SC 13G"],
                "accessionNumber": ["1", "2", "3", "4"],
                "filingDate": ["2026-08-14"] * 4,
                "reportDate": ["2026-06-30", "", "2026-06-30", ""],
                "primaryDocument": ["InfoTable.xml", "", "InfoTable.xml", ""],
            }
        }
    }
    records = parse_submissions(7, payload)
    assert [r.form_type for r in records] == ["13F-HR", "13F-HR/A"]
    assert records[1].is_amendment


def test_latest_n_quarters_window():
    records = [
        _record("2026-06-30", "a"),
        _record("2026-03-31", "b"),
        _record("2025-12-31", "c"),
        _record("2025-09-30", "d"),
        _record("2025-06-30", "e"),
        _record("2025-03-31", "f"),
        _record("2024-12-31", "g"),
        _record("2024-09-30", "h"),
        _record("2024-06-30", "i"),
        _record("2024-03-31", "j"),
        _record("2023-12-31", "k"),
        _record("2023-09-30", "l"),
        _record("2023-06-30", "m"),
    ]
    kept = latest_n_quarters(records, n=12)
    assert len(kept) == 12
    assert kept[-1].report_date == "2023-09-30"


def test_dedupe_effective_prefers_amendment():
    base = _record("2026-06-30", "A1")
    amend = FilingRecord(
        cik=1,
        accession_number="A2",
        form_type="13F-HR/A",
        filing_date="2026-08-20",
        report_date="2026-06-30",
        primary_document="InfoTable.xml",
    )
    chosen = dedupe_effective([base, amend])
    assert len(chosen) == 1
    assert chosen[0].accession_number == "A2"


def test_dedupe_effective_keeps_both_periods():
    records = [_record("2026-06-30", "A1"), _record("2026-03-31", "B1")]
    chosen = dedupe_effective(records)
    assert len(chosen) == 2


class _DiscoveryClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.urls = []

    @staticmethod
    def submissions_url(cik):
        return f"https://data.sec.gov/submissions/CIK{cik:010d}.json"

    def fetch_json(self, url):
        self.urls.append(url)
        return self.payloads[url]


def _columns(*, accession, report_date, accepted_at, form="13F-HR"):
    return {
        "form": [form],
        "accessionNumber": [accession],
        "filingDate": [accepted_at[:10]],
        "reportDate": [report_date],
        "acceptanceDateTime": [accepted_at],
        "primaryDocument": ["primary_doc.xml"],
    }


def _empty_columns():
    return {name: [] for name in ('form', 'accessionNumber', 'filingDate',
                                  'reportDate', 'acceptanceDateTime', 'primaryDocument')}


def test_discovery_follows_historical_submission_files():
    main_url = "https://data.sec.gov/submissions/CIK0000000001.json"
    history_name = "CIK0000000001-submissions-001.json"
    history_url = f"https://data.sec.gov/submissions/{history_name}"
    client = _DiscoveryClient(
        {
            main_url: {
                "filings": {
                    "recent": _columns(
                        accession="0000000001-26-000002",
                        report_date="2026-06-30",
                        accepted_at="2026-08-14T12:00:00.000Z",
                    ),
                    "files": [{"name": history_name}],
                }
            },
            history_url: _columns(
                accession="0000000001-25-000001",
                report_date="2025-12-31",
                accepted_at="2026-02-14T12:00:00.000Z",
            ),
        }
    )
    records = discover_filings(client, 1, quarters=12, as_of=date(2026, 9, 5))
    assert [r.accession_number for r in records] == [
        "0000000001-26-000002",
        "0000000001-25-000001",
    ]
    assert records[1].accepted_at == "2026-02-14T12:00:00.000Z"
    assert records[1].submission_source_url == history_url
    assert client.urls == [main_url, history_url]


def test_discovery_deduplicates_accessions_deterministically():
    main_url = "https://data.sec.gov/submissions/CIK0000000001.json"
    history_name = "CIK0000000001-submissions-001.json"
    history_url = f"https://data.sec.gov/submissions/{history_name}"
    duplicate = _columns(
        accession="0000000001-26-000002",
        report_date="2026-06-30",
        accepted_at="2026-08-14T12:00:00.000Z",
    )
    client = _DiscoveryClient(
        {
            main_url: {
                "filings": {"recent": duplicate, "files": [{"name": history_name}]}
            },
            history_url: duplicate,
        }
    )
    records = discover_filings(client, 1, quarters=12, as_of=date(2026, 9, 5))
    assert len(records) == 1
    assert records[0].submission_source_url == main_url


def test_latest_n_quarters_uses_as_of_not_latest_stale_record():
    records = [_record("2022-12-31", "old")]
    assert latest_n_quarters(records, n=12, as_of=date(2026, 9, 5)) == []


def test_ingest_rejects_empty_verified_manager_set(tmp_path, capsys):
    from argparse import Namespace
    from thirteenf.cli import cmd_ingest

    managers = tmp_path / 'managers.csv'
    managers.write_text('label,cik,validation_status\nExcluded,1,EXCLUDED\n', encoding='utf-8')
    args = Namespace(managers=str(managers), raw_root=str(tmp_path / 'raw'),
                     ua=None, release_mode=False, rate_limit_rps=1,
                     max_retries=0, quarters=12, force=False)
    assert cmd_ingest(args) == 1
    assert 'no eligible managers' in capsys.readouterr().out


def test_discovery_skips_shards_filed_before_report_window():
    main_url = _DiscoveryClient.submissions_url(1)
    payload = {'filings': {'recent': _empty_columns(), 'files': [
        {'name': 'CIK0000000001-submissions-001.json', 'filingTo': '2023-06-30'}]}}
    client = _DiscoveryClient({main_url: payload})
    assert discover_filings(client, 1, as_of=date(2026, 9, 7)) == []
    assert client.urls == [main_url]


@pytest.mark.parametrize('column,value', [
    ('reportDate', '2026-03-31'), ('filingDate', '2026-08-15'),
    ('form', '13F-HR/A'), ('primaryDocument', 'different.xml'),
    ('acceptanceDateTime', '2026-08-14T13:00:00.000Z')])
def test_conflicting_duplicate_accession_fails_closed(column, value):
    import copy
    from thirteenf.sec_client import SecError

    main_url = _DiscoveryClient.submissions_url(1)
    name = 'CIK0000000001-submissions-001.json'
    original = _columns(accession='0000000001-26-000002', report_date='2026-06-30',
                        accepted_at='2026-08-14T12:00:00.000Z')
    changed = copy.deepcopy(original)
    changed[column] = [value]
    client = _DiscoveryClient({
        main_url: {'filings': {'recent': original, 'files': [{'name': name}]}},
        f'https://data.sec.gov/submissions/{name}': changed})
    with pytest.raises(SecError, match='conflicting accession'):
        discover_filings(client, 1, as_of=date(2026, 9, 7))


def test_discovery_preserves_submissions_bytes_and_source_identity(tmp_path):
    from thirteenf.raw_store import RawStore
    from thirteenf.sec_client import SecResponse

    url = _DiscoveryClient.submissions_url(1)
    body = json.dumps({'filings': {'recent': _columns(
        accession='0000000001-26-000002', report_date='2026-06-30',
        accepted_at='2026-08-14T12:00:00.000Z'), 'files': []}}).encode()
    class Client(_DiscoveryClient):
        def fetch_bytes(self, url):
            return SecResponse(url, url, 200, body, '2026-09-07T00:00:00Z')
    records = discover_filings(Client({}), 1, as_of=date(2026, 9, 7), raw_root=tmp_path)
    manifests = list((tmp_path / 'discovery' / '0000000001').glob('*.json'))
    assert len(manifests) == 1
    evidence = json.loads(manifests[0].read_text())
    assert evidence['source_url'] == url
    assert evidence['fetched_at_utc'] == '2026-09-07T00:00:00Z'
    assert RawStore(tmp_path).read_object(evidence['object_path'], evidence['checksum']) == body
    assert records[0].submission_source_checksum == evidence['checksum']
    runs = list((tmp_path / 'discovery_runs' / '0000000001').glob('*.json'))
    assert len(runs) == 1
    inventory = json.loads(runs[0].read_text())
    assert inventory['status'] == 'COMPLETE'
    assert inventory['as_of'] == '2026-09-07'
    assert inventory['quarters'] == 12
    assert inventory['eligible_accessions'][0]['accession_number'] == records[0].accession_number
    assert inventory['sources'][0]['checksum'] == evidence['checksum']


def test_failed_discovery_has_incomplete_inventory(tmp_path):
    from thirteenf.sec_client import SecError

    class Client(_DiscoveryClient):
        def fetch_bytes(self, url):
            raise SecError('HTTP 403')
    with pytest.raises(SecError, match='403'):
        discover_filings(Client({}), 1, as_of=date(2026, 9, 7), raw_root=tmp_path)
    inventory = json.loads(next((tmp_path / 'discovery_runs' / '0000000001').glob('*.json')).read_text())
    assert inventory['status'] == 'INCOMPLETE'
    assert inventory['error'] == 'HTTP 403'


def test_later_filed_historical_amendment_remains_in_report_window():
    main_url = _DiscoveryClient.submissions_url(1)
    name = 'CIK0000000001-submissions-001.json'
    client = _DiscoveryClient({
        main_url: {'filings': {'recent': _empty_columns(), 'files': [
            {'name': name, 'filingFrom': '2026-08-20', 'filingTo': '2026-08-21'}]}},
        f'https://data.sec.gov/submissions/{name}': _columns(
            accession='0000000001-26-000002', report_date='2023-09-30',
            accepted_at='2026-08-21T12:00:00.000Z', form='13F-HR/A')})
    assert len(discover_filings(client, 1, as_of=date(2026, 9, 7))) == 1


def test_ingest_empty_filing_window_is_failure(tmp_path, monkeypatch, capsys):
    from thirteenf import cli

    managers = tmp_path / 'managers.csv'
    managers.write_text('label,cik,validation_status\nTracked,1,VERIFIED\n', encoding='utf-8')
    monkeypatch.setattr(cli, 'discover_filings', lambda *a, **kw: [])
    assert cli.main(['ingest', '--managers', str(managers), '--raw-root', str(tmp_path / 'raw')]) == 1
    assert 'raw_files=0 failures=1' in capsys.readouterr().out


@pytest.mark.parametrize('bad', [{}, {'form': '13F-HR'}, {'form': []}, {'form': {}}])
def test_bad_history_schema_does_not_hide_behind_valid_recent_filings(bad):
    from thirteenf.sec_client import SecError
    main_url = _DiscoveryClient.submissions_url(1)
    name = 'CIK0000000001-submissions-001.json'
    client = _DiscoveryClient({
        main_url: {'filings': {'recent': _columns(
            accession='0000000001-26-000002', report_date='2026-06-30',
            accepted_at='2026-08-14T12:00:00.000Z'), 'files': [{'name': name}]}},
        f'https://data.sec.gov/submissions/{name}': bad})
    with pytest.raises(SecError, match='submissions'):
        discover_filings(client, 1, as_of=date(2026, 9, 7))


@pytest.mark.parametrize('recent', [[], None, 'invalid'])
def test_main_submissions_requires_recent_object(recent):
    from thirteenf.sec_client import SecError
    with pytest.raises(SecError, match='submissions'):
        parse_submissions(1, {'filings': {'recent': recent}})


def test_history_name_must_belong_to_requested_cik():
    from thirteenf.sec_client import SecError
    url = _DiscoveryClient.submissions_url(1)
    client = _DiscoveryClient({url: {'filings': {'recent': _empty_columns(),
        'files': [{'name': 'CIK0000000002-submissions-001.json'}]}}})
    with pytest.raises(SecError, match='historical submissions'):
        discover_filings(client, 1)
