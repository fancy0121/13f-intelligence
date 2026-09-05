from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.filings import FilingRecord, download_filing
from thirteenf.raw_store import RawStore
from thirteenf.sec_client import SecResponse


INFO_XML_A = b"<informationTable><infoTable><cusip>000000001</cusip></infoTable></informationTable>"
INFO_XML_B = b"<informationTable><infoTable><cusip>000000002</cusip></infoTable></informationTable>"
COVER_XML = b"""<edgarSubmission><headerData><submissionType>13F-HR/A</submissionType></headerData>
<formData><coverPage><reportCalendarOrQuarter>06-30-2026</reportCalendarOrQuarter>
<isAmendment>true</isAmendment><amendmentNo>1</amendmentNo>
<amendmentInfo><amendmentType>RESTATEMENT</amendmentType></amendmentInfo>
</coverPage></formData></edgarSubmission>"""


def _record(form_type="13F-HR"):
    return FilingRecord(
        cik=1,
        accession_number="0000000001-26-000001",
        form_type=form_type,
        filing_date="2026-08-14",
        report_date="2026-06-30",
        primary_document="primary_doc.xml",
        accepted_at="2026-08-14T12:00:00.000Z",
        submission_source_url="https://data.sec.gov/submissions/CIK0000000001.json",
    )


class _DownloadClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    @staticmethod
    def archive_url(cik, accession, name):
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{name}"

    @staticmethod
    def archive_index_url(cik, accession):
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/index.json"

    def fetch_bytes(self, url, *, etag=None, last_modified=None):
        self.calls.append((url, etag, last_modified))
        status, body, response_etag = self.responses.pop(0)
        return SecResponse(
            url=url,
            final_url=url,
            status=status,
            body=body,
            fetched_at_utc="2026-09-05T10:00:00+00:00",
            etag=response_etag,
            last_modified="Fri, 05 Sep 2026 10:00:00 GMT",
        )

    def fetch_json(self, url):
        raise AssertionError(f"unexpected index request: {url}")


def test_identical_bytes_share_one_content_object(tmp_path):
    store = RawStore(tmp_path)
    first = store.put(b"same")
    second = store.put(b"same")
    assert first == second
    assert (tmp_path / first.relative_path).read_bytes() == b"same"
    assert len(list((tmp_path / "objects" / "sha256").rglob("*"))) >= 2


def test_changed_accession_content_keeps_both_objects_and_manifest_versions(tmp_path):
    store = RawStore(tmp_path)
    first = store.put(INFO_XML_A)
    first_manifest = store.write_manifest(
        1, "0000000001-26-000001", {"status": "OK", "object_path": first.relative_path}
    )
    second = store.put(INFO_XML_B)
    second_manifest = store.write_manifest(
        1, "0000000001-26-000001", {"status": "OK", "object_path": second.relative_path}
    )
    assert first.relative_path != second.relative_path
    assert (tmp_path / first.relative_path).read_bytes() == INFO_XML_A
    assert (tmp_path / second.relative_path).read_bytes() == INFO_XML_B
    assert first_manifest == second_manifest
    versions = list(
        (tmp_path / "manifest_versions" / "0000000001" / "000000000126000001").glob("*.json")
    )
    assert len(versions) == 2


def test_manifest_identity_rejects_path_traversal(tmp_path):
    store = RawStore(tmp_path)
    with pytest.raises(ValueError, match="accession"):
        store.write_manifest(1, "../../escape", {"status": "OK"})


def test_download_writes_content_object_and_real_fetch_metadata(tmp_path):
    client = _DownloadClient([(200, INFO_XML_A, '"v1"')])
    raw = download_filing(client, _record(), tmp_path)
    manifest = json.loads(raw.manifest_path.read_text(encoding="utf-8"))
    assert raw.raw_path.read_bytes() == INFO_XML_A
    assert (tmp_path / manifest["object_path"]).read_bytes() == INFO_XML_A
    assert manifest["fetched_at_utc"] == "2026-09-05T10:00:00+00:00"
    assert manifest["etag"] == '"v1"'
    assert manifest["checksum"] == raw.checksum


def test_download_revalidates_cached_source_with_conditional_request(tmp_path):
    first = _DownloadClient([(200, INFO_XML_A, '"v1"')])
    initial = download_filing(first, _record(), tmp_path)
    second = _DownloadClient([(304, b"", '"v1"')])
    cached = download_filing(second, _record(), tmp_path)
    assert cached.checksum == initial.checksum
    assert second.calls[0][1] == '"v1"'


def test_download_changed_content_preserves_old_object(tmp_path):
    download_filing(_DownloadClient([(200, INFO_XML_A, '"v1"')]), _record(), tmp_path)
    changed = download_filing(_DownloadClient([(200, INFO_XML_B, '"v2"')]), _record(), tmp_path)
    assert changed.raw_path.read_bytes() == INFO_XML_B
    objects = [p for p in (tmp_path / "objects" / "sha256").rglob("*") if p.is_file()]
    assert len(objects) == 2


class _SeparateComponentsClient(_DownloadClient):
    def fetch_json(self, url):
        return {
            "directory": {
                "item": [
                    {"name": "primary_doc.xml", "size": str(len(COVER_XML))},
                    {"name": "info_table.xml", "size": str(len(INFO_XML_A))},
                ]
            }
        }


def test_download_preserves_primary_cover_and_information_table(tmp_path):
    client = _SeparateComponentsClient(
        [(200, COVER_XML, '"cover-v1"'), (200, INFO_XML_A, '"info-v1"')]
    )
    raw = download_filing(client, _record("13F-HR/A"), tmp_path)
    manifest = json.loads(raw.manifest_path.read_text(encoding="utf-8"))

    assert raw.primary_path is not None
    assert raw.primary_path.read_bytes() == COVER_XML
    assert raw.raw_path.read_bytes() == INFO_XML_A
    assert manifest["components"]["primary_document"]["checksum"] != manifest["components"]["information_table"]["checksum"]
    assert (tmp_path / manifest["components"]["primary_document"]["object_path"]).read_bytes() == COVER_XML
