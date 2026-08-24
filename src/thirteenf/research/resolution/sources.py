"""Provider clients: OpenFIGI mapping + SEC company-ticker files.

Network access is encapsulated here; pure parsing helpers are unit-testable
without network.
"""

from __future__ import annotations

import hashlib
import gzip
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from thirteenf.research.resolution.models import OpenFIGIRecord, OpenFIGIResponse


OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# US venue exchange codes observed for US-listed equity share classes.
US_EXCHANGES = frozenset(
    {
        "US", "UN", "UA", "UC", "UP", "UB", "UM", "UX", "UD", "UW", "UF", "UQ",
    }
)


def parse_openfigi_entry(entry: dict, id_type: str, id_value: str) -> OpenFIGIResponse:
    """Convert one OpenFIGI mapping response entry into a typed response."""
    if entry is None:
        return OpenFIGIResponse(id_type=id_type, id_value=id_value, error="no_entry")
    if entry.get("error"):
        return OpenFIGIResponse(
            id_type=id_type, id_value=id_value, error=str(entry["error"])
        )
    records = []
    for it in entry.get("data") or []:
        records.append(
            OpenFIGIRecord(
                figi=it.get("figi"),
                compositeFIGI=it.get("compositeFIGI"),
                shareClassFIGI=it.get("shareClassFIGI"),
                ticker=it.get("ticker"),
                exchCode=it.get("exchCode"),
                securityType=it.get("securityType"),
                marketSector=it.get("marketSector"),
                name=it.get("name"),
                securityDescription=it.get("securityDescription"),
            )
        )
    return OpenFIGIResponse(
        id_type=id_type, id_value=id_value, records=tuple(records)
    )


def us_filter(records: tuple[OpenFIGIRecord, ...]) -> list[OpenFIGIRecord]:
    return [r for r in records if (r.exchCode or "").upper() in US_EXCHANGES]


def distinct_us_tickers(records: tuple[OpenFIGIRecord, ...]) -> list[str]:
    return sorted({r.ticker for r in us_filter(records) if r.ticker})


def _cache_key(id_type: str, id_value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{id_type}_{id_value}")
    return safe


class OpenFIGIClient:
    """OpenFIGI anonymous mapping client with cache, batching, retries."""

    def __init__(
        self,
        cache_dir: Path | str,
        *,
        sleep_s: float = 0.25,
        max_retries: int = 3,
        batch_size: int = 10,
        transport=None,
        user_agent: str = "13f-intelligence-research/0.2.1 (research; local audit)",
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sleep_s = sleep_s
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.user_agent = user_agent
        self._transport = transport or self._default_transport

    def _default_transport(self, payload: bytes) -> tuple[int, bytes]:
        req = urllib.request.Request(
            OPENFIGI_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()

    def _post(self, jobs: list[dict]) -> list[dict]:
        payload = json.dumps(jobs).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                status, body = self._transport(payload)
                if status == 200:
                    return json.loads(body.decode("utf-8"))
                if status in (429, 500, 502, 503, 504):
                    last_error = RuntimeError(f"HTTP {status}")
                else:
                    last_error = RuntimeError(f"HTTP {status}")
            except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
                last_error = exc
            if attempt < self.max_retries:
                time.sleep(self.sleep_s * (2**attempt) + 1.0)
        raise last_error if last_error else RuntimeError("openfigi transport failed")

    def mapping(self, jobs: list[dict]) -> list[OpenFIGIResponse]:
        """Resolve jobs (list of {'idType','idValue'}) -> responses, cached."""
        out: list[OpenFIGIResponse | None] = [None] * len(jobs)
        pending: list[tuple[int, dict]] = []
        for idx, job in enumerate(jobs):
            id_type = job["idType"]
            id_value = job["idValue"]
            cache_file = self.cache_dir / f"{_cache_key(id_type, id_value)}.json"
            if cache_file.exists():
                try:
                    cached = json.loads(cache_file.read_text(encoding="utf-8"))
                    entry = cached.get("entry") if isinstance(cached, dict) else cached
                    out[idx] = parse_openfigi_entry(entry, id_type, id_value)
                    continue
                except (ValueError, OSError):
                    pass
            pending.append((idx, job))
        for start in range(0, len(pending), self.batch_size):
            chunk = pending[start : start + self.batch_size]
            try:
                results = self._post([j for _, j in chunk])
            except Exception as exc:  # noqa: BLE001 - deterministic error record
                for idx, job in chunk:
                    out[idx] = OpenFIGIResponse(
                        id_type=job["idType"],
                        id_value=job["idValue"],
                        error=f"transport_error:{exc}",
                    )
                continue
            for (idx, job), entry in zip(chunk, results):
                resp = parse_openfigi_entry(entry, job["idType"], job["idValue"])
                out[idx] = resp
                cache_file = self.cache_dir / f"{_cache_key(job['idType'], job['idValue'])}.json"
                try:
                    cache_file.write_text(
                        json.dumps(
                            {
                                "idType": job["idType"],
                                "idValue": job["idValue"],
                                "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "entry": entry,
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                except OSError:
                    pass
            if start + self.batch_size < len(pending):
                time.sleep(self.sleep_s)
        return [o for o in out if o is not None]  # type: ignore[return-value]

    def mapping_one(self, id_type: str, id_value: str) -> OpenFIGIResponse:
        return self.mapping([{"idType": id_type, "idValue": id_value}])[0]


# ---------------------------------------------------------------------------
# SEC company-ticker files
# ---------------------------------------------------------------------------

ABBREV_EXPAND = {
    "CORP": "CORPORATION",
    "CO": "COMPANY",
    "INC": "INCORPORATED",
    "FINL": "FINANCIAL",
    "ENTMT": "ENTERTAINMENT",
    "LTD": "LIMITED",
    "DEL": "DELAWARE",
    "HOLDING": "HOLDINGS",
    "HOLDGS": "HOLDINGS",
    "MNFG": "MANUFACTURING",
    "MFG": "MANUFACTURING",
    "MANUFAC": "MANUFACTURING",
    "SVC": "SERVICES",
    "SVCS": "SERVICES",
    "INDS": "INDUSTRIES",
    "IND": "INDUSTRIES",
    "GRP": "GROUP",
    "PHARMA": "PHARMACEUTICAL",
    "TECH": "TECHNOLOGY",
    "SEMICOND": "SEMICONDUCTOR",
    "SEMI": "SEMICONDUCTOR",
    "INVT": "INVESTMENT",
    "MTG": "MORTGAGE",
}


def raw_norm(value: str | None) -> str:
    s = (value or "").upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", s)).strip()


def canonical_norm(value: str | None) -> str:
    s = raw_norm(value)
    toks = []
    for t in s.split():
        toks.append(ABBREV_EXPAND.get(t, t))
    return " ".join(toks)


def names_match(a: str | None, b: str | None) -> bool:
    """Deterministic, conservative issuer-name equality for corroboration."""
    ra = raw_norm(a)
    rb = raw_norm(b)
    if not ra or not rb:
        return False
    if ra == rb:
        return True
    if canonical_norm(a) == canonical_norm(b):
        return True
    ta = ra.split()
    tb = rb.split()
    if len(ta) >= 2 and len(tb) >= 2:
        if ta == tb[: len(ta)] or tb == ta[: len(tb)]:
            return True
        if set(ta) <= set(tb) or set(tb) <= set(ta):
            return True
    return False


def _read_json_bytes(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def load_company_tickers(path: Path | str) -> list[dict]:
    data = _read_json_bytes(Path(path))
    out = []
    for rec in data.values():
        if isinstance(rec, dict) and "ticker" in rec:
            out.append(
                {
                    "cik": str(rec.get("cik_str", "")),
                    "ticker": rec.get("ticker", ""),
                    "title": rec.get("title", ""),
                    "exchange": "",
                }
            )
    return out


def load_company_tickers_exchange(path: Path | str) -> list[dict]:
    data = _read_json_bytes(Path(path))
    fields = data.get("fields") or []
    out = []
    for row in data.get("data") or []:
        d = dict(zip(fields, row))
        out.append(
            {
                "cik": str(d.get("cik", "")),
                "ticker": d.get("ticker", ""),
                "title": d.get("name", ""),
                "exchange": d.get("exchange", ""),
            }
        )
    return out


class SECIndex:
    """Issuer-name -> SEC ticker records index (current ticker only)."""

    def __init__(self, records: list[dict]) -> None:
        self.records = records
        self._by_raw: dict[str, list[dict]] = {}
        self._by_canonical: dict[str, list[dict]] = {}
        for rec in records:
            title = rec.get("title")
            key = raw_norm(title)
            if key:
                self._by_raw.setdefault(key, []).append(rec)
            ckey = canonical_norm(title)
            if ckey:
                self._by_canonical.setdefault(ckey, []).append(rec)

    @classmethod
    def build(cls, tickers_path: Path | str, exchange_path: Path | str) -> "SECIndex":
        recs = load_company_tickers(tickers_path)
        recs += load_company_tickers_exchange(exchange_path)
        return cls(recs)

    def lookup(self, issuer: str | None) -> list[dict]:
        key = raw_norm(issuer)
        if not key:
            return []
        out = self._by_raw.get(key, [])
        if not out:
            out = self._by_canonical.get(canonical_norm(issuer), [])
        if not out:
            toks = key.split()
            if len(toks) >= 3:
                prefix = " ".join(toks[:3])
                out = [
                    r
                    for k, rs in self._by_raw.items()
                    if k.startswith(prefix)
                    for r in rs
                ][:8]
        return out

    def unique_ticker(self, issuer: str | None) -> str | None:
        tickers = {r.get("ticker") for r in self.lookup(issuer) if r.get("ticker")}
        return next(iter(tickers)) if len(tickers) == 1 else None

    def lookup_by_title(self, name: str | None) -> list[dict]:
        """Find SEC records whose normalized title matches the given name."""
        key = raw_norm(name)
        if not key:
            return []
        out = self._by_raw.get(key, [])
        if not out:
            out = self._by_canonical.get(canonical_norm(name), [])
        if not out:
            toks = key.split()
            if len(toks) >= 2:
                prefix = " ".join(toks[:2])
                out = [
                    r
                    for k, rs in self._by_raw.items()
                    if k.startswith(prefix)
                    for r in rs
                ][:8]
        return out

    def ticker_set_for_title(self, name: str | None) -> set[str]:
        return {r.get("ticker") for r in self.lookup_by_title(name) if r.get("ticker")}

    def corroborates(self, issuer: str | None, of_name: str | None) -> bool:
        """True when any SEC record title matches the issuer or OpenFIGI name."""
        if not issuer:
            return False
        for rec in self.lookup(issuer):
            title = rec.get("title")
            if names_match(title, issuer) or names_match(title, of_name):
                return True
        return False
