from __future__ import annotations

import gzip
import json
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from thirteenf.sec_client import SecClient, SecError


class _FakeResponse:
    def __init__(self, status: int, body: bytes, headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _install_opener(monkeypatch, responses):
    """responses: list of (status, body) consumed in order."""
    calls = {"n": 0}

    class _Opener:
        def open(self, req, timeout=None):
            idx = calls["n"]
            calls["n"] += 1
            status, body = responses[min(idx, len(responses) - 1)]
            if status >= 400:
                raise urllib.error.HTTPError(
                    req.full_url, status, "Error", {}, None
                )
            return _FakeResponse(status, body)

    monkeypatch.setattr("urllib.request.urlopen", _Opener().open)
    return calls


def test_fetch_json_decodes_gzip(monkeypatch):
    payload = {"name": "TEST", "cik": 123}
    body = gzip.compress(json.dumps(payload).encode("utf-8"))
    _install_opener(monkeypatch, [(200, body)])
    client = SecClient(user_agent="test@example.com", rate_limit_s=1000)
    assert client.fetch_json("https://example.invalid/x.json") == payload


def test_retries_on_429_then_succeeds(monkeypatch):
    body = gzip.compress(json.dumps({"ok": True}).encode("utf-8"))
    calls = _install_opener(monkeypatch, [(429, b"{}"), (200, body)])
    client = SecClient(
        user_agent="test@example.com", rate_limit_s=1000, max_retries=3
    )
    assert client.fetch_json("https://example.invalid/x.json") == {"ok": True}
    assert calls["n"] == 2


def test_raises_after_max_retries(monkeypatch):
    _install_opener(monkeypatch, [(429, b"{}")])
    client = SecClient(
        user_agent="test@example.com", rate_limit_s=1000, max_retries=2
    )
    with pytest.raises(SecError):
        client.fetch_json("https://example.invalid/x.json")


def test_http_404_raises_immediately(monkeypatch):
    _install_opener(monkeypatch, [(404, b"")])
    client = SecClient(user_agent="test@example.com", rate_limit_s=1000)
    with pytest.raises(SecError):
        client.fetch_json("https://example.invalid/x.json")


def test_archive_url_format():
    client = SecClient(user_agent="test@example.com")
    url = client.archive_url(1067983, "0000950123-26-000001", "info_table.xml")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/1067983/"
        "000095012326000001/info_table.xml"
    )
