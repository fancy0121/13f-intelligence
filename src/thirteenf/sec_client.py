"""Compliant SEC EDGAR HTTP client.

Implements:
  - explicit User-Agent (required by SEC fair-access policy)
  - global rate limiting (default 2 requests/second, conservative)
  - retries with exponential backoff + jitter, honoring Retry-After
  - transparent gzip decompression
  - deterministic local caching (see filings.py)

This module performs no analysis; it only fetches bytes/JSON from SEC.
"""

from __future__ import annotations

import gzip
import io
import json
import math
import os
import random
import re
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
    final_url: str
    status: int
    body: bytes
    fetched_at_utc: str
    etag: str | None = None
    last_modified: str | None = None


SEC_ALLOWED_HOSTS = frozenset({"sec.gov", "www.sec.gov", "data.sec.gov"})
DEFAULT_RATE_LIMIT_RPS = 2.0
DEFAULT_MAX_RESPONSE_BYTES = 25_000_000
DEFAULT_MAX_DECOMPRESSED_BYTES = 100_000_000


def validate_release_user_agent(value: str) -> str:
    """Require a named, reachable contact for unattended SEC requests."""
    normalized = value.strip()
    lowered = normalized.lower()
    email = re.search(r"\b[^@\s]+@[^@\s]+\.[^@\s]+\b", normalized)
    if not normalized or email is None or "example.com" in lowered:
        raise ValueError("SEC_USER_AGENT must contain a real contact name and email")
    return normalized


class _SecRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Check BEFORE urllib sends the next request (including contact headers).
        SecClient._validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_sec_url(request, *, timeout):
    return urllib.request.build_opener(_SecRedirectHandler()).open(request, timeout=timeout)


class SecClient:
    def __init__(
        self,
        user_agent: str | None = None,
        rate_limit_rps: float | None = None,
        max_retries: int | None = None,
        timeout: float = 30.0,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES,
    ) -> None:
        self.user_agent = user_agent or os.getenv(
            "SEC_USER_AGENT",
            "13F Intelligence Research contact@example.com",
        )
        raw_rate = (
            os.getenv("SEC_RATE_LIMIT_RPS", str(DEFAULT_RATE_LIMIT_RPS))
            if rate_limit_rps is None
            else rate_limit_rps
        )
        self.rate_limit_rps = float(raw_rate)
        if not math.isfinite(self.rate_limit_rps) or not 0 < self.rate_limit_rps <= 10:
            raise ValueError("rate_limit_rps must be finite and in the range (0, 10]")
        self.max_retries = (
            int(os.getenv("SEC_MAX_RETRIES", "5"))
            if max_retries is None
            else int(max_retries)
        )
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if timeout <= 0 or not math.isfinite(timeout):
            raise ValueError("timeout must be finite and > 0")
        if max_response_bytes <= 0 or max_decompressed_bytes <= 0:
            raise ValueError("response size limits must be > 0")
        self.timeout = timeout
        self.max_response_bytes = int(max_response_bytes)
        self.max_decompressed_bytes = int(max_decompressed_bytes)
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = (1.0 / self.rate_limit_rps) - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _validate_url(url: str) -> None:
        try:
            parsed = urllib.parse.urlsplit(url)
            allowed = (parsed.scheme == "https" and parsed.hostname in SEC_ALLOWED_HOSTS
                       and parsed.port in (None, 443) and parsed.username is None
                       and parsed.password is None)
        except ValueError:
            allowed = False
        if not allowed:
            raise SecError(f"unapproved SEC host for {url}")

    def _read_limited(self, response) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(min(64 * 1024, self.max_response_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > self.max_response_bytes:
                raise SecError(f"SEC response too large for {response.geturl()}")
            chunks.append(chunk)
        return b"".join(chunks)

    def _decompress_limited(self, body: bytes, url: str) -> bytes:
        if body[:2] != b"\x1f\x8b":
            return body
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
                decoded = stream.read(self.max_decompressed_bytes + 1)
        except (OSError, EOFError) as exc:
            raise SecError(f"invalid gzip response from {url}") from exc
        if len(decoded) > self.max_decompressed_bytes:
            raise SecError(f"SEC decompressed response too large for {url}")
        return decoded

    @staticmethod
    def _fetched_at() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _request(
        self,
        url: str,
        retries: int | None = None,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> SecResponse:
        self._validate_url(url)
        try:
            validate_release_user_agent(self.user_agent)
        except ValueError as exc:
            raise SecError(str(exc)) from exc
        retries = self.max_retries if retries is None else retries
        attempt = 0
        while True:
            self._throttle()
            headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip"}
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified
            req = urllib.request.Request(url, headers=headers)
            try:
                with open_sec_url(req, timeout=self.timeout) as resp:
                    status = resp.status
                    final_url = resp.geturl()
                    self._validate_url(final_url)
                    if status < 200 or status >= 300:
                        raise SecError(f"SEC HTTP {status} for {url}")
                    body = self._decompress_limited(
                        self._read_limited(resp), final_url
                    )
                    return SecResponse(
                        url=url,
                        final_url=final_url,
                        status=status,
                        body=body,
                        fetched_at_utc=self._fetched_at(),
                        etag=resp.headers.get("ETag"),
                        last_modified=resp.headers.get("Last-Modified"),
                    )
            except urllib.error.HTTPError as exc:
                if exc.code == 304:
                    final_url = exc.geturl()
                    self._validate_url(final_url)
                    return SecResponse(
                        url=url,
                        final_url=final_url,
                        status=304,
                        body=b"",
                        fetched_at_utc=self._fetched_at(),
                        etag=exc.headers.get("ETag"),
                        last_modified=exc.headers.get("Last-Modified"),
                    )
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
                delay = float(retry_after)
                if math.isfinite(delay) and delay >= 0:
                    return min(delay, 60.0)
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

    def fetch_bytes(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> SecResponse:
        return self._request(url, etag=etag, last_modified=last_modified)

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
