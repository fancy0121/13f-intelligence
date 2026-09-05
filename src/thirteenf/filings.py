"""SEC 13F filing discovery and raw preservation.

Responsibilities:
  - discover 13F-HR / 13F-HR/A filings from the submissions JSON index
  - download the INFORMATION TABLE document for a filing
  - persist raw bytes + manifest (checksum, source URL, timestamps)
  - idempotent: existing raw + matching checksum => skip download
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote

from thirteenf.raw_store import RawStore
from thirteenf.sec_client import SecClient, SecError, SecResponse

THIRTEEN_F_FORMS = ("13F-HR", "13F-HR/A")
INFO_TABLE_RE = re.compile(rb"<\w*:?informationTable")


@dataclass(frozen=True)
class FilingRecord:
    cik: int
    accession_number: str
    form_type: str
    filing_date: str
    report_date: str
    primary_document: str
    accepted_at: str = ""
    submission_source_url: str = ""

    @property
    def is_amendment(self) -> bool:
        return self.form_type == "13F-HR/A"

    @property
    def raw_dir_name(self) -> str:
        return self.accession_number.replace("-", "")


@dataclass(frozen=True)
class RawFiling:
    filing: FilingRecord
    raw_path: Path
    manifest_path: Path
    checksum: str
    source_url: str


def parse_submissions(
    cik: int,
    payload: dict,
    source_url: str = "",
) -> list[FilingRecord]:
    """Extract 13F filings from a recent or historical submissions payload."""
    records: list[FilingRecord] = []
    recent = payload.get("filings", {}).get("recent")
    if recent is None:
        recent = payload
    if not isinstance(recent, dict):
        return records
    forms = recent.get("form", []) or []
    accession = recent.get("accessionNumber", []) or []
    filing_dates = recent.get("filingDate", []) or []
    report_dates = recent.get("reportDate", []) or []
    primary_docs = recent.get("primaryDocument", []) or []
    accepted_times = recent.get("acceptanceDateTime", []) or []
    for i, form in enumerate(forms):
        if form not in THIRTEEN_F_FORMS:
            continue
        required = (accession, filing_dates, report_dates, primary_docs)
        if any(i >= len(values) for values in required):
            raise SecError(f"misaligned submissions columns for CIK {cik}")
        records.append(
            FilingRecord(
                cik=cik,
                accession_number=accession[i],
                form_type=form,
                filing_date=filing_dates[i],
                report_date=report_dates[i],
                primary_document=primary_docs[i],
                accepted_at=(
                    accepted_times[i] if i < len(accepted_times) else ""
                ),
                submission_source_url=source_url,
            )
        )
    return records


def _quarter_end_for_as_of(as_of: date) -> date:
    import calendar

    end_month = ((as_of.month - 1) // 3 + 1) * 3
    candidate = date(
        as_of.year,
        end_month,
        calendar.monthrange(as_of.year, end_month)[1],
    )
    if candidate <= as_of:
        return candidate
    previous_month = end_month - 3
    year = as_of.year
    if previous_month <= 0:
        previous_month += 12
        year -= 1
    return date(year, previous_month, calendar.monthrange(year, previous_month)[1])


def _shift_quarter_end(value: date, quarters: int) -> date:
    import calendar

    absolute_month = value.year * 12 + (value.month - 1) + quarters * 3
    year, month_zero = divmod(absolute_month, 12)
    month = month_zero + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def latest_n_quarters(
    records: list[FilingRecord], n: int = 12, as_of: date | None = None
) -> list[FilingRecord]:
    """Keep only filings whose report period is within the last n quarters.

    A filing is eligible if report_date >= end of (latest quarter - n + 1).
    Records are ordered newest-first as returned by SEC.
    """
    if not records or n <= 0:
        return []
    as_of = as_of or date.today()
    newest_end = _quarter_end_for_as_of(as_of)
    oldest_end = _shift_quarter_end(newest_end, -(n - 1))
    return [
        r
        for r in records
        if oldest_end <= date.fromisoformat(r.report_date) <= newest_end
    ]


HISTORICAL_SUBMISSIONS_RE = re.compile(
    r"^CIK\d{10}-submissions-\d{3}\.json$"
)


def discover_filings(
    client: SecClient,
    cik: int,
    quarters: int = 12,
    as_of: date | None = None,
) -> list[FilingRecord]:
    """Discover the complete 13F window across recent and history shards."""
    main_url = client.submissions_url(cik)
    payload = client.fetch_json(main_url)
    records = parse_submissions(cik, payload, main_url)
    history_files = payload.get("filings", {}).get("files", []) or []
    for item in history_files:
        name = str(item.get("name") or "")
        if not HISTORICAL_SUBMISSIONS_RE.fullmatch(name):
            raise SecError(f"invalid historical submissions file for CIK {cik}: {name}")
        url = f"https://data.sec.gov/submissions/{quote(name)}"
        records.extend(parse_submissions(cik, client.fetch_json(url), url))

    by_accession: dict[str, FilingRecord] = {}
    for record in records:
        by_accession.setdefault(record.accession_number, record)
    eligible = latest_n_quarters(
        list(by_accession.values()),
        n=quarters,
        as_of=as_of,
    )
    return sorted(
        eligible,
        key=lambda r: (r.report_date, r.accepted_at, r.accession_number),
        reverse=True,
    )


def dedupe_effective(records: list[FilingRecord]) -> list[FilingRecord]:
    """Select the effective filing per (report_period, form family).

    13F-HR/A amendments supersede the original 13F-HR for the same report
    period; when both exist, keep the amendment (newest filing_date wins).
    Both raw filings are preserved; this only decides which one feeds the
    analysis layer.
    """
    by_period: dict[str, list[FilingRecord]] = {}
    for r in records:
        by_period.setdefault(r.report_date, []).append(r)
    chosen: list[FilingRecord] = []
    for period, group in by_period.items():
        base = [r for r in group if not r.is_amendment]
        amendments = sorted(
            (r for r in group if r.is_amendment),
            key=lambda r: r.filing_date,
        )
        if amendments:
            chosen.append(amendments[-1])
        elif base:
            chosen.append(max(base, key=lambda r: r.filing_date))
    return chosen


def download_filing(
    client: SecClient,
    filing: FilingRecord,
    raw_root: Path,
    force: bool = False,
) -> RawFiling:
    """Download, revalidate, and preserve an INFORMATION TABLE."""
    store = RawStore(raw_root)
    manifest = store.load_manifest(filing.cik, filing.accession_number)
    cached_body: bytes | None = None
    if manifest:
        checksum = str(manifest.get("checksum") or "")
        object_path = str(manifest.get("object_path") or "")
        try:
            if checksum and object_path:
                cached_body = store.read_object(object_path, checksum)
            else:
                legacy = store.legacy_manifest_path(
                    filing.cik, filing.accession_number
                ).parent / "info_table.xml"
                if legacy.exists() and checksum:
                    candidate = legacy.read_bytes()
                    if _sha256(candidate) == checksum:
                        cached_body = candidate
        except (OSError, RuntimeError):
            cached_body = None
        if cached_body is not None and not INFO_TABLE_RE.search(cached_body):
            cached_body = None

    if not force and cached_body is not None and manifest:
        source_url = str(
            manifest.get("final_url") or manifest.get("source_url") or ""
        )
        if source_url:
            response = client.fetch_bytes(
                source_url,
                etag=manifest.get("etag"),
                last_modified=manifest.get("last_modified"),
            )
            if response.status == 304:
                return _persist_info_table(
                    store,
                    filing,
                    response,
                    cached_body,
                    prior_manifest=manifest,
                )
            if INFO_TABLE_RE.search(response.body):
                return _persist_info_table(
                    store,
                    filing,
                    response,
                    response.body,
                    prior_manifest=manifest,
                )

    response = _fetch_info_table(client, filing)
    if response is None:
        manifest_path = store.write_manifest(
            filing.cik,
            filing.accession_number,
            {
                "cik": filing.cik,
                "accession": filing.accession_number,
                "form_type": filing.form_type,
                "filing_date": filing.filing_date,
                "report_date": filing.report_date,
                "accepted_at": filing.accepted_at,
                "submission_source_url": filing.submission_source_url,
                "source_url": "",
                "status": "NO_INFO_TABLE",
                "error": "no INFORMATION TABLE XML found in accession",
                "fetched_at_utc": None,
            },
        )
        raise SecError(
            f"No INFORMATION TABLE for {filing.accession_number}; "
            f"manifest={manifest_path}"
        )
    return _persist_info_table(store, filing, response, response.body)


def _persist_info_table(
    store: RawStore,
    filing: FilingRecord,
    response: SecResponse,
    body: bytes,
    prior_manifest: dict | None = None,
) -> RawFiling:
    obj = store.put(body)
    legacy_path = store.materialize_legacy(
        filing.cik,
        filing.accession_number,
        "info_table.xml",
        body,
    )
    payload = {
        "cik": filing.cik,
        "accession": filing.accession_number,
        "form_type": filing.form_type,
        "filing_date": filing.filing_date,
        "report_date": filing.report_date,
        "accepted_at": filing.accepted_at,
        "submission_source_url": filing.submission_source_url,
        "source_url": response.url,
        "final_url": response.final_url,
        "status": "OK",
        "checksum": obj.checksum,
        "object_path": obj.relative_path,
        "logical_path": legacy_path.relative_to(store.root).as_posix(),
        "byte_size": obj.byte_size,
        "fetched_at_utc": response.fetched_at_utc,
        "etag": response.etag or (prior_manifest or {}).get("etag"),
        "last_modified": response.last_modified
        or (prior_manifest or {}).get("last_modified"),
    }
    manifest_path = store.write_manifest(
        filing.cik, filing.accession_number, payload
    )
    return RawFiling(
        filing=filing,
        raw_path=legacy_path,
        manifest_path=manifest_path,
        checksum=obj.checksum,
        source_url=response.final_url,
    )


def _fetch_info_table(
    client: SecClient, filing: FilingRecord
) -> SecResponse | None:
    """Locate and download the INFORMATION TABLE XML for a filing.

    Strategy:
      1. Try the primary document (some filers make it the info table).
      2. If it is not an information table, list the accession directory and
         try the largest .xml file (the info table is usually the big one).
    Returns the SEC response or None when no info table is found.
    """
    # 1. primary document
    primary_url = client.archive_url(
        filing.cik, filing.accession_number, filing.primary_document
    )
    try:
        resp = client.fetch_bytes(primary_url)
        if INFO_TABLE_RE.search(resp.body):
            return resp
    except SecError:
        pass

    # 2. accession directory index
    try:
        index_url = client.archive_index_url(filing.cik, filing.accession_number)
        index = client.fetch_json(index_url)
        items = index.get("directory", {}).get("item", [])
    except SecError:
        return None

    xml_items = [
        it for it in items if (it.get("name") or "").lower().endswith(".xml")
    ]
    # Prefer the largest .xml (the info table is the big one).
    xml_items.sort(key=lambda it: int(it.get("size") or 0), reverse=True)
    for item in xml_items:
        name = item["name"]
        if name == filing.primary_document:
            continue
        url = client.archive_url(filing.cik, filing.accession_number, name)
        try:
            resp = client.fetch_bytes(url)
            if INFO_TABLE_RE.search(resp.body):
                return resp
        except SecError:
            continue
    return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
