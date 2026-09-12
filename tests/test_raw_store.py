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


def test_cached_information_table_does_not_hide_changed_cover(tmp_path):
    record = _record('13F-HR/A')
    first = _SeparateComponentsClient([(200, COVER_XML, '"c1"'), (200, INFO_XML_A, '"i1"')])
    original = download_filing(first, record, tmp_path)
    changed_cover = COVER_XML.replace(b'RESTATEMENT', b'NEW HOLDINGS')
    class Revalidator(_SeparateComponentsClient):
        def fetch_bytes(self, url, **headers):
            self.calls.append((url, headers))
            body = changed_cover if url.endswith('primary_doc.xml') else b''
            return SecResponse(url, url, 200 if body else 304, body,
                               '2026-09-07T00:00:00Z', '"c2"' if body else '"i1"')
    client = Revalidator([])
    refreshed = download_filing(client, record, tmp_path)
    assert refreshed.primary_checksum != original.primary_checksum
    assert refreshed.primary_path.read_bytes() == changed_cover
    assert len(client.calls) == 2


def test_missing_cover_cannot_be_successful_information_table_download(tmp_path):
    from thirteenf.sec_client import SecError

    class MissingCover(_SeparateComponentsClient):
        def fetch_bytes(self, url, **headers):
            if url.endswith('primary_doc.xml'):
                raise SecError('HTTP 403 for primary document')
            return super().fetch_bytes(url, **headers)

    client = MissingCover([(200, INFO_XML_A, '"i1"')])
    with pytest.raises(SecError, match='primary document'):
        download_filing(client, _record(), tmp_path)
    manifest = RawStore(tmp_path).load_manifest(1, _record().accession_number)
    assert manifest['status'] == 'NO_PRIMARY_DOCUMENT'


@pytest.mark.parametrize('prefix', ['xslForm13F_X01/', 'xslForm13F_X02/'])
def test_primary_download_uses_raw_xml_not_sec_html_display(tmp_path, prefix):
    from dataclasses import replace

    record = replace(_record(), primary_document=prefix + 'primary_doc.xml')
    client = _SeparateComponentsClient([(200, COVER_XML, '"c1"'), (200, INFO_XML_A, '"i1"')])
    raw = download_filing(client, record, tmp_path)
    assert client.calls[0][0].endswith('/000000000126000001/primary_doc.xml')
    assert raw.primary_path.read_bytes() == COVER_XML


def test_cached_html_display_url_is_refetched_as_raw_xml(tmp_path):
    from dataclasses import replace

    record = replace(_record(), primary_document='xslForm13F_X02/primary_doc.xml')
    client = _SeparateComponentsClient([(200, COVER_XML, '"c1"'), (200, INFO_XML_A, '"i1"')])
    download_filing(client, record, tmp_path)
    store = RawStore(tmp_path)
    manifest = store.load_manifest(1, record.accession_number)
    primary = manifest['components']['primary_document']
    old_url = client.archive_url(1, record.accession_number, record.primary_document)
    primary['source_url'] = primary['final_url'] = old_url
    store.write_manifest(1, record.accession_number, manifest)
    fresh = _SeparateComponentsClient([(200, COVER_XML, '"c2"'), (200, INFO_XML_A, '"i1"')])
    raw = download_filing(fresh, record, tmp_path)
    assert fresh.calls[0][0].endswith('/000000000126000001/primary_doc.xml')
    updated = json.loads(raw.manifest_path.read_text(encoding='utf-8'))
    assert '/xslForm13F_' not in updated['components']['primary_document']['source_url']


def test_directory_missing_attachment_uses_filename_from_full_sec_submission(tmp_path):
    submission = (b'<SEC-DOCUMENT>\n<DOCUMENT>\n<TYPE>INFORMATION TABLE\n'
                  b'<SEQUENCE>2\n<FILENAME>XML_Infotable.xml\n<TEXT>\n<XML>\n'
                  + INFO_XML_A + b'\n</XML>\n</TEXT>\n</DOCUMENT>\n</SEC-DOCUMENT>')
    class MissingIndex(_DownloadClient):
        def fetch_json(self, url):
            return {'directory': {'item': [{'name': 'primary_doc.xml', 'size': '100'}]}}
    client = MissingIndex([(200, COVER_XML, '"c1"'), (200, submission, '"s1"'),
                           (200, INFO_XML_A, '"i1"')])
    raw = download_filing(client, _record(), tmp_path)
    assert client.calls[-1][0].endswith('/XML_Infotable.xml')
    manifest = json.loads(raw.manifest_path.read_text())
    locator = manifest['components']['complete_submission']
    assert RawStore(tmp_path).read_object(locator['object_path'], locator['checksum']) == submission


@pytest.mark.parametrize('name', ['../outside.xml', 'https://evil.example/x.xml', 'nested/table.xml'])
def test_full_submission_attachment_name_cannot_escape_accession(tmp_path, name):
    from thirteenf.sec_client import SecError
    submission = f'<DOCUMENT>\n<TYPE>INFORMATION TABLE\n<FILENAME>{name}\n<TEXT>xml</TEXT>\n</DOCUMENT>'.encode()
    class MissingIndex(_DownloadClient):
        def fetch_json(self, url):
            return {'directory': {'item': []}}
    client = MissingIndex([(200, COVER_XML, '"c1"'), (200, submission, '"s1"')])
    with pytest.raises(SecError):
        download_filing(client, _record(), tmp_path)
    assert len(client.calls) == 2
