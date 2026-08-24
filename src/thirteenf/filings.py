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
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from thirteenf.sec_client import SecClient, SecError

THIRTEEN_F_FORMS = ("13F-HR", "13F-HR/A")


@dataclass(frozen=True)
class FilingRecord:
    cik: int
    accession_number: str
    form_type: str
    filing_date: str
    report_date: str
    primary_document: str

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


def parse_submissions(cik: int, payload: dict) -> list[FilingRecord]:
    """Extract 13F filings from a submissions JSON payload."""
    records: list[FilingRecord] = []
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    accession = recent.get("accessionNumber", []) or []
    filing_dates = recent.get("filingDate", []) or []
    report_dates = recent.get("reportDate", []) or []
    primary_docs = recent.get("primaryDocument", []) or []
    for i, form in enumerate(forms):
        if form not in THIRTEEN_F_FORMS:
            continue
        records.append(
            FilingRecord(
                cik=cik,
                accession_number=accession[i],
                form_type=form,
                filing_date=filing_dates[i],
                report_date=report_dates[i],
                primary_document=primary_docs[i],
            )
        )
    return records


def latest_n_quarters(
    records: list[FilingRecord], n: int = 12, as_of: date | None = None
) -> list[FilingRecord]:
    """Keep only filings whose report period is within the last n quarters.

    A filing is eligible if report_date >= end of (latest quarter - n + 1).
    Records are ordered newest-first as returned by SEC.
    """
    if not records:
        return []
    as_of = as_of or date.today()
    latest_report = max(date.fromisoformat(r.report_date) for r in records)
    # Quarter end of latest report, minus (n-1) quarters.
    quarter_end = latest_report.replace(day=1)
    # Walk back months to the quarter start.
    def _quarter_end(d: date) -> date:
        q = (d.month - 1) // 3
        end_month = (q + 1) * 3
        return date(d.year, end_month, 1) if False else _quarter_end_date(d)

    def _quarter_end_date(d: date) -> date:
        q = (d.month - 1) // 3
        end_month = (q + 1) * 3
        import calendar

        return date(d.year, end_month, calendar.monthrange(d.year, end_month)[1])

    oldest_end = _quarter_end_date(quarter_end)
    for _ in range(n - 1):
        y = oldest_end.year
        m = oldest_end.month - 3
        if m <= 0:
            y -= 1
            m += 12
        oldest_end = _quarter_end_date(date(y, m, 1))
    return [
        r
        for r in records
        if date.fromisoformat(r.report_date) >= oldest_end
    ]


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
    """Download and persist the INFORMATION TABLE for a filing (idempotent)."""
    raw_dir = raw_root / str(filing.cik) / filing.raw_dir_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "info_table.xml"
    manifest_path = raw_dir / "manifest.json"

    if not force and raw_path.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("checksum") == _sha256(raw_path.read_bytes()):
            return RawFiling(
                filing=filing,
                raw_path=raw_path,
                manifest_path=manifest_path,
                checksum=manifest["checksum"],
                source_url=manifest["source_url"],
            )

    source_url = client.archive_url(
        filing.cik, filing.accession_number, filing.primary_document
    )
    try:
        resp = client.fetch_bytes(source_url)
    except SecError as exc:
        # Write a failed manifest so we can surface FAILED_INGESTION later.
        manifest_path.write_text(
            json.dumps(
                {
                    "cik": filing.cik,
                    "accession": filing.accession_number,
                    "form_type": filing.form_type,
                    "filing_date": filing.filing_date,
                    "report_date": filing.report_date,
                    "source_url": source_url,
                    "status": "FAILED",
                    "error": str(exc),
                    "fetched_at_utc": None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        raise

    raw_path.write_bytes(resp.body)
    checksum = _sha256(resp.body)
    manifest_path.write_text(
        json.dumps(
            {
                "cik": filing.cik,
                "accession": filing.accession_number,
                "form_type": filing.form_type,
                "filing_date": filing.filing_date,
                "report_date": filing.report_date,
                "source_url": source_url,
                "status": "OK",
                "checksum": checksum,
                "fetched_at_utc": resp.fetched_at_utc,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return RawFiling(
        filing=filing,
        raw_path=raw_path,
        manifest_path=manifest_path,
        checksum=checksum,
        source_url=source_url,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

