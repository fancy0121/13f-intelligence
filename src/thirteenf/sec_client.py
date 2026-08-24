"""Compliant SEC EDGAR HTTP client.

Implements:
  - explicit User-Agent (required by SEC fair-access policy)
  - global rate limiting (default 5 req/s, conservative)
  - retries with exponential backoff + jitter, honoring Retry-After
  - transparent gzip decompression
  - deterministic local caching (see filings.py)

This module performs no analysis; it only fetches bytes/JSON from SEC.
"""

from __future__ import annotations

import gzip
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone


class SecError(RuntimeError):
    """Raised when SEC cannot be reached after retries or returns an error."""


@dataclass(frozen=True)
class SecResponse:
    url: str
    status: int
    body: bytes
    fetched_at_utc: str


class SecClient:
    def __init__(
        self,
        user_agent: str | None = None,
        rate_limit_s: float | None = None,
        max_retries: int = 5,
        timeout: float = 30.0,
    ) -> None:
        self.user_agent = user_agent or os.getenv(
            "SEC_USER_AGENT",
            "13F Intelligence Research contact@example.com",
        )
        self.rate_limit_s = rate_limit_s or float(os.getenv("SEC_RATE_LIMIT_RPS", "5"))
        self.max_retries = max_retries or int(os.getenv("SEC_MAX_RETRIES", "5"))
        self.timeout = timeout
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = (1.0 / self.rate_limit_s) - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _request(self, url: str, retries: int | None = None) -> SecResponse:
        retries = self.max_retries if retries is None else retries
        attempt = 0
        while True:
            self._throttle()
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status = resp.status
                    body = resp.read()
                    if body[:2] == b"\x1f\x8b":
                        body = gzip.decompress(body)
                    return SecResponse(
                        url=url,
                        status=status,
                        body=body,
                        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
                    )
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                    delay = self._backoff(attempt, exc.headers.get("Retry-After"))
                    time.sleep(delay)
                    attempt += 1
                    continue
                if exc.code in (404, 403, 400):
                    raise SecError(f"SEC HTTP {exc.code} for {url}") from exc
                raise SecError(f"SEC HTTP {exc.code} for {url}") from exc
            except (urllib.error.URLError, OSError) as exc:
                if attempt < retries:
                    time.sleep(self._backoff(attempt))
                    attempt += 1
                    continue
                raise SecError(f"SEC unreachable: {url}: {exc}") from exc

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
        base = 2.0 ** attempt
        return min(base + random.uniform(0, 0.5), 60.0)

    def fetch_json(self, url: str) -> dict:
        resp = self._request(url)
        try:
            return json.loads(resp.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SecError(f"Invalid JSON from {url}: {exc}") from exc

    def fetch_bytes(self, url: str) -> SecResponse:
        return self._request(url)

    def submissions_url(self, cik: int) -> str:
        return f"https://data.sec.gov/submissions/CIK{cik:010d}.json"

    def archive_url(self, cik: int, accession: str, primary_document: str) -> str:
        accession_no_dashes = accession.replace("-", "")
        return (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{cik}/{accession_no_dashes}/{urllib.parse.quote(primary_document)}"
        )

    def archive_index_url(self, cik: int, accession: str) -> str:
        accession_no_dashes = accession.replace("-", "")
        return (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{cik}/{accession_no_dashes}/index.json"
        )
