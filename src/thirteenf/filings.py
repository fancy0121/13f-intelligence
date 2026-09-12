"""SEC 13F filing discovery and raw preservation.

Responsibilities:
  - discover 13F-HR / 13F-HR/A filings from the submissions JSON index
  - download the INFORMATION TABLE document for a filing
  - persist raw bytes + manifest (checksum, source URL, timestamps)
  - idempotent: existing raw + matching checksum => skip download
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

from thirteenf.raw_store import RawObject, RawStore
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
    submission_source_checksum: str = ""

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
    primary_path: Path | None = None
    primary_checksum: str | None = None


def parse_submissions(
    cik: int,
    payload: dict,
    source_url: str = "",
) -> list[FilingRecord]:
    """Extract 13F filings from a recent or historical submissions payload."""
    records: list[FilingRecord] = []
    if not isinstance(payload, dict):
        raise SecError(f"invalid submissions object for CIK {cik}")
    recent = payload
    if "filings" in payload:
        filings = payload["filings"]
        if not isinstance(filings, dict):
            raise SecError(f"invalid submissions filings for CIK {cik}")
        recent = filings.get("recent")
        if "files" in filings and not isinstance(filings["files"], list):
            raise SecError(f"invalid submissions history list for CIK {cik}")
    if not isinstance(recent, dict):
        raise SecError(f"invalid submissions recent object for CIK {cik}")
    required_names = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    if any(not isinstance(recent.get(name), list) for name in required_names):
        raise SecError(f"invalid submissions column arrays for CIK {cik}")
    count = len(recent["form"])
    if any(len(recent[name]) != count for name in required_names):
        raise SecError(f"misaligned submissions columns for CIK {cik}")
    if "acceptanceDateTime" in recent and (
        not isinstance(recent["acceptanceDateTime"], list)
        or len(recent["acceptanceDateTime"]) != count
    ):
        raise SecError(f"misaligned submissions acceptance timestamps for CIK {cik}")
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
    raw_root: Path | None = None,
) -> list[FilingRecord]:
    """Preserve the source inventory; COMPLETE means discovery, not ingestion."""
    as_of = as_of or date.today()
    inventory = {
        "schema_version": 2,
        "cik": cik, "as_of": as_of.isoformat(), "quarters": quarters,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "INCOMPLETE", "sources": [], "skipped_shards": [],
        "eligible_accessions": [],
    }
    try:
        records = _discover_filings(client, cik, quarters, as_of, raw_root, inventory)
        inventory.update(status="COMPLETE", eligible_accessions=[asdict(r) for r in records])
        return records
    except Exception as exc:
        inventory["error"] = str(exc)
        raise
    finally:
        inventory["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        if raw_root is not None:
            RawStore(raw_root).write_discovery_inventory(cik, inventory)


def _discover_filings(
    client: SecClient, cik: int, quarters: int, as_of: date,
    raw_root: Path | None, inventory: dict,
) -> list[FilingRecord]:
    """Discover the complete 13F window across recent and history shards."""
    if quarters <= 0:
        raise SecError("quarters must be positive")
    as_of = as_of or date.today()
    oldest_end = _shift_quarter_end(_quarter_end_for_as_of(as_of), -(quarters - 1))
    store = RawStore(raw_root) if raw_root is not None else None

    def fetch(url: str) -> tuple[dict, str]:
        if store is None:
            return client.fetch_json(url), ""
        response = client.fetch_bytes(url)
        obj = store.put(response.body)
        source = {
            "cik": cik, "source_url": url, "final_url": response.final_url,
            "http_status": response.status, "fetched_at_utc": response.fetched_at_utc,
            "checksum": obj.checksum, "object_path": obj.relative_path,
            "byte_size": obj.byte_size,
        }
        store.write_discovery_manifest(cik, source)
        inventory['sources'].append(source)
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SecError(f"invalid submissions JSON: {url}") from exc
        if not isinstance(payload, dict):
            raise SecError(f"submissions JSON must be an object: {url}")
        return payload, obj.checksum

    def parse(payload: dict, url: str, checksum: str) -> list[FilingRecord]:
        return [replace(r, submission_source_checksum=checksum)
                for r in parse_submissions(cik, payload, url)]

    main_url = client.submissions_url(cik)
    payload, checksum = fetch(main_url)
    records = parse(payload, main_url, checksum)
    history_files = payload.get("filings", {}).get("files", []) or []
    for item in history_files:
        if not isinstance(item, dict):
            raise SecError(f"invalid historical submissions entry for CIK {cik}")
        name = str(item.get("name") or "")
        if (not HISTORICAL_SUBMISSIONS_RE.fullmatch(name)
                or not name.startswith(f"CIK{cik:010d}-submissions-")):
            raise SecError(f"invalid historical submissions file for CIK {cik}: {name}")
        # Filing dates, not report dates: never exclude a later-filed amendment.
        # Missing date metadata is conservative: fetch the shard instead.
        if item.get("filingTo"):
            try:
                filing_to = date.fromisoformat(item["filingTo"])
            except (TypeError, ValueError) as exc:
                raise SecError(f"invalid historical filingTo for CIK {cik}") from exc
            if filing_to < oldest_end:
                inventory['skipped_shards'].append({**item, 'reason': 'filed_before_report_window'})
                continue
        url = f"https://data.sec.gov/submissions/{quote(name)}"
        shard, checksum = fetch(url)
        records.extend(parse(shard, url, checksum))

    by_accession: dict[str, FilingRecord] = {}
    for record in records:
        previous = by_accession.get(record.accession_number)
        if previous is not None and replace(
            previous, submission_source_url="", submission_source_checksum=""
        ) != replace(record, submission_source_url="", submission_source_checksum=""):
            raise SecError(f"conflicting accession metadata: {record.accession_number}")
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


def _raw_primary_document(name: str) -> str:
    # SEC's XSL presentation path returns HTML, not the source XML. Strip only
    # this known 13F display prefix; never rewrite arbitrary document paths.
    match = re.fullmatch(r"xslForm13F_X\d{2}/([^/]+\.xml)", name)
    return match.group(1) if match else name


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

    components = manifest.get("components") if manifest else None
    has_primary_component = (
        isinstance(components, dict)
        and isinstance(components.get("primary_document"), dict)
    )
    if has_primary_component:
        primary = components['primary_document']
        expected_url = client.archive_url(
            filing.cik, filing.accession_number, _raw_primary_document(filing.primary_document)
        )
        # Old caches may contain an HTML presentation as the cover. Refetch
        # rather than reuse its validators; immutable old objects remain intact.
        has_primary_component = primary.get('source_url') == expected_url
    if (
        not force
        and cached_body is not None
        and manifest
        and has_primary_component
    ):
        source_url = str(
            manifest.get("final_url") or manifest.get("source_url") or ""
        )
        if source_url:
            response = client.fetch_bytes(
                source_url,
                etag=manifest.get("etag"),
                last_modified=manifest.get("last_modified"),
            )
            # Cover semantics can change independently of the holdings bytes.
            # Every refresh must revalidate both authoritative components.
            primary = components['primary_document']
            primary_url = str(primary.get('final_url') or primary.get('source_url') or '')
            if not primary_url:
                raise SecError('cached filing has no primary document URL')
            if primary_url == source_url:
                primary_response = replace(response, body=cached_body) if response.status == 304 else response
            else:
                primary_response = client.fetch_bytes(
                    primary_url, etag=primary.get('etag'),
                    last_modified=primary.get('last_modified'))
                if primary_response.status == 304:
                    prior_body = store.read_object(primary['object_path'], primary['checksum'])
                    primary_response = replace(primary_response, body=prior_body)
            if response.status == 304:
                return _persist_info_table(
                    store,
                    filing,
                    response,
                    cached_body,
                    prior_manifest=manifest,
                    primary_response=primary_response,
                )
            if INFO_TABLE_RE.search(response.body):
                return _persist_info_table(
                    store,
                    filing,
                    response,
                    response.body,
                    prior_manifest=manifest,
                    primary_response=primary_response,
                )

    primary_response, response, submission_response = _fetch_filing_components(client, filing)
    if primary_response is None or response is None:
        primary_component = None
        if primary_response is not None:
            primary_component = _persist_component(
                store,
                filing,
                logical_name="primary_document.xml",
                response=primary_response,
                body=primary_response.body,
            )
        error = "no INFORMATION TABLE XML found in accession"
        status = "NO_INFO_TABLE"
        if primary_response is None:
            error = "primary document could not be retrieved"
            status = "NO_PRIMARY_DOCUMENT"
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
                "submission_source_checksum": filing.submission_source_checksum,
                "source_url": "",
                "status": status,
                "error": error,
                "fetched_at_utc": None,
                "components": (
                    {"primary_document": primary_component}
                    if primary_component is not None
                    else {}
                ),
            },
        )
        raise SecError(
            f"{error} for {filing.accession_number}; "
            f"manifest={manifest_path}"
        )
    return _persist_info_table(
        store,
        filing,
        response,
        response.body,
        primary_response=primary_response,
        submission_response=submission_response,
    )


def _persist_info_table(
    store: RawStore,
    filing: FilingRecord,
    response: SecResponse,
    body: bytes,
    prior_manifest: dict | None = None,
    primary_response: SecResponse | None = None,
    submission_response: SecResponse | None = None,
) -> RawFiling:
    obj = store.put(body)
    legacy_path = store.materialize_legacy(
        filing.cik,
        filing.accession_number,
        "info_table.xml",
        body,
    )
    prior_components = (prior_manifest or {}).get("components") or {}
    components = (
        dict(prior_components) if isinstance(prior_components, dict) else {}
    )
    if primary_response is not None:
        components["primary_document"] = _persist_component(
            store,
            filing,
            logical_name="primary_document.xml",
            response=primary_response,
            body=primary_response.body,
        )
    if submission_response is not None:
        components["complete_submission"] = _persist_component(
            store, filing, logical_name="submission.txt", response=submission_response,
            body=submission_response.body,
        )
        components["complete_submission"]["document_name"] = filing.accession_number + ".txt"
    components["information_table"] = _component_payload(
        obj=obj,
        logical_path=legacy_path,
        store=store,
        response=response,
        document_name=response.final_url.rsplit("/", 1)[-1].split("?", 1)[0],
        prior=(
            prior_components.get("information_table", {})
            if isinstance(prior_components, dict)
            else {}
        ),
    )
    payload = {
        "cik": filing.cik,
        "accession": filing.accession_number,
        "form_type": filing.form_type,
        "filing_date": filing.filing_date,
        "report_date": filing.report_date,
        "accepted_at": filing.accepted_at,
        "submission_source_url": filing.submission_source_url,
        "submission_source_checksum": filing.submission_source_checksum,
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
        "components": components,
    }
    manifest_path = store.write_manifest(
        filing.cik, filing.accession_number, payload
    )
    primary = components.get("primary_document") or {}
    primary_logical_path = primary.get("logical_path")
    return RawFiling(
        filing=filing,
        raw_path=legacy_path,
        manifest_path=manifest_path,
        checksum=obj.checksum,
        source_url=response.final_url,
        primary_path=(
            _safe_stored_path(store, primary_logical_path)
            if primary_logical_path
            else None
        ),
        primary_checksum=primary.get("checksum"),
    )


def _persist_component(
    store: RawStore,
    filing: FilingRecord,
    *,
    logical_name: str,
    response: SecResponse,
    body: bytes,
) -> dict:
    obj = store.put(body)
    logical_path = store.materialize_legacy(
        filing.cik,
        filing.accession_number,
        logical_name,
        body,
    )
    return _component_payload(
        obj=obj,
        logical_path=logical_path,
        store=store,
        response=response,
        document_name=filing.primary_document,
        prior={},
    )


def _component_payload(
    *,
    obj: RawObject,
    logical_path: Path,
    store: RawStore,
    response: SecResponse,
    document_name: str,
    prior: dict,
) -> dict:
    return {
        "document_name": document_name,
        "source_url": response.url,
        "final_url": response.final_url,
        "checksum": obj.checksum,
        "object_path": obj.relative_path,
        "logical_path": logical_path.relative_to(store.root).as_posix(),
        "byte_size": obj.byte_size,
        "fetched_at_utc": response.fetched_at_utc,
        "etag": response.etag or prior.get("etag"),
        "last_modified": response.last_modified or prior.get("last_modified"),
    }


def _safe_stored_path(store: RawStore, relative_path: str) -> Path:
    candidate = (store.root / relative_path).resolve()
    if candidate != store.root and store.root not in candidate.parents:
        raise RuntimeError(f"raw manifest path escapes root: {relative_path}")
    return candidate


def _fetch_filing_components(
    client: SecClient, filing: FilingRecord
) -> tuple[SecResponse | None, SecResponse | None, SecResponse | None]:
    """Locate and download the INFORMATION TABLE XML for a filing.

    Strategy:
      1. Try the primary document (some filers make it the info table).
      2. If it is not an information table, list the accession directory and
         try the largest .xml file (the info table is usually the big one).
    Returns ``(primary document, information table, optional locator submission)``. The first two are the
    same response when the primary document itself is the information table.
    """
    # 1. primary document
    primary_url = client.archive_url(
        filing.cik, filing.accession_number, _raw_primary_document(filing.primary_document)
    )
    primary_response: SecResponse | None = None
    try:
        primary_response = client.fetch_bytes(primary_url)
        if INFO_TABLE_RE.search(primary_response.body):
            return primary_response, primary_response, None
    except SecError:
        # A table without its cover cannot establish amendment semantics or
        # reported totals. Do not continue and mislabel a partial filing OK.
        return None, None, None

    # 2. accession directory index
    try:
        index_url = client.archive_index_url(filing.cik, filing.accession_number)
        index = client.fetch_json(index_url)
        items = index.get("directory", {}).get("item", [])
    except SecError:
        return primary_response, None, None

    xml_items = [
        it for it in items if (it.get("name") or "").lower().endswith(".xml")
    ]
    # Prefer the largest .xml (the info table is the big one).
    xml_items.sort(key=lambda it: int(it.get("size") or 0), reverse=True)
    for item in xml_items:
        name = item["name"]
        if name == _raw_primary_document(filing.primary_document):
            continue
        url = client.archive_url(filing.cik, filing.accession_number, name)
        try:
            resp = client.fetch_bytes(url)
            if INFO_TABLE_RE.search(resp.body):
                return primary_response, resp, None
        except SecError:
            continue
    # Some SEC directory indexes omit a real attachment. Use only the exact
    # filename declared in this accession's complete submission, never guesses.
    submission = None
    try:
        submission = client.fetch_bytes(client.archive_url(
            filing.cik, filing.accession_number, filing.accession_number + ".txt"
        ))
        names = []
        for document in re.findall(br"<DOCUMENT>(.*?)</DOCUMENT>", submission.body, re.DOTALL):
            header = document.split(b"<TEXT>", 1)[0]
            if not re.search(br"<TYPE>[ \t]*INFORMATION TABLE[ \t]*\r?\n", header):
                continue
            name = re.search(br"<FILENAME>([^\r\n]+)", header)
            if name is None:
                raise SecError("INFORMATION TABLE filename is missing in complete submission")
            filename = name.group(1).strip().decode("ascii")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.xml", filename, re.IGNORECASE):
                raise SecError("unsafe INFORMATION TABLE filename in complete submission")
            names.append(filename)
        if len(names) == 1:
            resp = client.fetch_bytes(client.archive_url(filing.cik, filing.accession_number, names[0]))
            if INFO_TABLE_RE.search(resp.body):
                return primary_response, resp, submission
    except (SecError, UnicodeDecodeError):
        pass
    return primary_response, None, submission


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
