from __future__ import annotations

import gzip
import json
import math
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

import thirteenf.sec_client as sec_client_module
from thirteenf.cli import build_parser
from thirteenf.sec_client import SecClient, SecError


@pytest.mark.parametrize("url", ["https://attacker.test/data", "http://www.sec.gov/data",
                                 "https://www.sec.gov:8501/data", "https://user@www.sec.gov/data"])
def test_redirect_rejected_before_following_request(url):
    handler = sec_client_module._SecRedirectHandler()
    request = sec_client_module.urllib.request.Request("https://www.sec.gov/data")
    with pytest.raises(SecError, match="unapproved SEC host"):
        handler.redirect_request(request, None, 302, "redirect", {}, url)


def test_sec_redirect_handler_is_installed(monkeypatch):
    seen = []
    class Opener:
        def open(self, request, timeout):
            return "response"
    def build(*handlers):
        seen.extend(handlers)
        return Opener()
    monkeypatch.setattr(sec_client_module.urllib.request, "build_opener", build)
    assert sec_client_module.open_sec_url(object(), timeout=1) == "response"
    assert isinstance(seen[0], sec_client_module._SecRedirectHandler)


@pytest.mark.parametrize("value", ["-1", "NaN", "inf", "garbage"])
def test_malformed_retry_after_uses_finite_nonnegative_backoff(value):
    delay = SecClient._backoff(0, value)
    assert math.isfinite(delay) and 1 <= delay <= 1.5


class _FakeResponse:
    def __init__(
        self,
        status: int,
        body: bytes,
        headers=None,
        final_url: str = "https://www.sec.gov/test",
    ):
        self.status = status
        self._body = body
        self.headers = headers or {}
        self._offset = 0
        self._final_url = final_url

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._body[self._offset :]
            self._offset = len(self._body)
            return chunk
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self._final_url

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

    monkeypatch.setattr("thirteenf.sec_client.open_sec_url", _Opener().open)
    return calls


def test_fetch_json_decodes_gzip(monkeypatch):
    payload = {"name": "TEST", "cik": 123}
    body = gzip.compress(json.dumps(payload).encode("utf-8"))
    _install_opener(monkeypatch, [(200, body)])
    client = SecClient(user_agent="test@acme.test", rate_limit_rps=10)
    assert client.fetch_json("https://www.sec.gov/x.json") == payload


def test_retries_on_429_then_succeeds(monkeypatch):
    body = gzip.compress(json.dumps({"ok": True}).encode("utf-8"))
    calls = _install_opener(monkeypatch, [(429, b"{}"), (200, body)])
    client = SecClient(
        user_agent="test@acme.test", rate_limit_rps=10, max_retries=3
    )
    assert client.fetch_json("https://www.sec.gov/x.json") == {"ok": True}
    assert calls["n"] == 2


def test_raises_after_max_retries(monkeypatch):
    _install_opener(monkeypatch, [(429, b"{}")])
    client = SecClient(
        user_agent="test@acme.test", rate_limit_rps=10, max_retries=2
    )
    with pytest.raises(SecError):
        client.fetch_json("https://www.sec.gov/x.json")


def test_http_404_raises_immediately(monkeypatch):
    _install_opener(monkeypatch, [(404, b"")])
    client = SecClient(user_agent="test@acme.test", rate_limit_rps=10)
    with pytest.raises(SecError):
        client.fetch_json("https://www.sec.gov/x.json")


def test_archive_url_format():
    client = SecClient(user_agent="test@acme.test")
    url = client.archive_url(1067983, "0000950123-26-000001", "info_table.xml")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/1067983/"
        "000095012326000001/info_table.xml"
    )


def test_release_user_agent_rejects_placeholder():
    with pytest.raises(ValueError, match="real contact"):
        sec_client_module.validate_release_user_agent(
            "13F Intelligence Research contact@example.com"
        )


def test_release_user_agent_accepts_named_contact():
    value = "13F Research Operations ops@acme.test"
    assert sec_client_module.validate_release_user_agent(value) == value


def test_placeholder_is_blocked_before_any_network_even_outside_release(monkeypatch):
    calls = _install_opener(monkeypatch, [(200, b'{}')])
    with pytest.raises(SecError, match="contact"):
        SecClient(user_agent="contact@example.com").fetch_json("https://www.sec.gov/x.json")
    assert calls["n"] == 0


@pytest.mark.parametrize("rate", [0, -1, 10.1, math.inf, math.nan])
def test_rate_limit_rps_must_be_finite_and_bounded(rate):
    with pytest.raises(ValueError, match="rate_limit_rps"):
        SecClient(user_agent="test@acme.test", rate_limit_rps=rate)


def test_rate_limit_reads_environment_when_argument_absent(monkeypatch):
    monkeypatch.setenv("SEC_RATE_LIMIT_RPS", "3.5")
    client = SecClient(user_agent="test@acme.test", rate_limit_rps=None)
    assert client.rate_limit_rps == 3.5


def test_redirect_outside_sec_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "thirteenf.sec_client.open_sec_url",
        lambda req, timeout=None: _FakeResponse(
            200,
            b"data",
            final_url="https://attacker.invalid/file.xml",
        ),
    )
    client = SecClient(user_agent="test@acme.test", rate_limit_rps=10)
    with pytest.raises(SecError, match="unapproved SEC host"):
        client.fetch_bytes("https://www.sec.gov/file.xml")


def test_unapproved_requested_host_is_rejected_before_network(monkeypatch):
    called = {"value": False}

    def opener(req, timeout=None):
        called["value"] = True
        return _FakeResponse(200, b"data")

    monkeypatch.setattr("thirteenf.sec_client.open_sec_url", opener)
    client = SecClient(user_agent="test@acme.test", rate_limit_rps=10)
    with pytest.raises(SecError, match="unapproved SEC host"):
        client.fetch_bytes("https://attacker.invalid/file.xml")
    assert called["value"] is False


def test_response_size_limit_is_enforced(monkeypatch):
    _install_opener(monkeypatch, [(200, b"12345")])
    client = SecClient(
        user_agent="test@acme.test",
        rate_limit_rps=10,
        max_response_bytes=4,
    )
    with pytest.raises(SecError, match="response too large"):
        client.fetch_bytes("https://www.sec.gov/file.xml")


def test_gzip_expansion_limit_is_enforced(monkeypatch):
    _install_opener(monkeypatch, [(200, gzip.compress(b"expanded"))])
    client = SecClient(
        user_agent="test@acme.test",
        rate_limit_rps=10,
        max_decompressed_bytes=4,
    )
    with pytest.raises(SecError, match="decompressed response too large"):
        client.fetch_bytes("https://www.sec.gov/file.xml")


def test_response_metadata_and_conditional_headers(monkeypatch):
    captured = {}

    def opener(req, timeout=None):
        captured["etag"] = req.get_header("If-none-match")
        captured["modified"] = req.get_header("If-modified-since")
        return _FakeResponse(
            200,
            b"data",
            headers={"ETag": '"abc"', "Last-Modified": "Fri, 04 Sep 2026 12:00:00 GMT"},
            final_url="https://www.sec.gov/final.xml",
        )

    monkeypatch.setattr("thirteenf.sec_client.open_sec_url", opener)
    client = SecClient(user_agent="test@acme.test", rate_limit_rps=10)
    response = client.fetch_bytes(
        "https://www.sec.gov/file.xml",
        etag='"old"',
        last_modified="Thu, 03 Sep 2026 12:00:00 GMT",
    )
    assert captured == {
        "etag": '"old"',
        "modified": "Thu, 03 Sep 2026 12:00:00 GMT",
    }
    assert response.final_url == "https://www.sec.gov/final.xml"
    assert response.etag == '"abc"'
    assert response.last_modified == "Fri, 04 Sep 2026 12:00:00 GMT"
    assert response.fetched_at_utc.endswith("+00:00")


def test_not_modified_returns_metadata_response(monkeypatch):
    def opener(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url,
            304,
            "Not Modified",
            {"ETag": '"same"'},
            None,
        )

    monkeypatch.setattr("thirteenf.sec_client.open_sec_url", opener)
    client = SecClient(user_agent="test@acme.test", rate_limit_rps=10)
    response = client.fetch_bytes("https://www.sec.gov/file.xml", etag='"same"')
    assert response.status == 304
    assert response.body == b""
    assert response.etag == '"same"'


def test_zero_max_retries_does_not_retry(monkeypatch):
    calls = _install_opener(monkeypatch, [(429, b"{}"), (200, b"{}")])
    client = SecClient(
        user_agent="test@acme.test",
        rate_limit_rps=10,
        max_retries=0,
    )
    with pytest.raises(SecError):
        client.fetch_json("https://www.sec.gov/x.json")
    assert calls["n"] == 1


def test_ingest_cli_uses_rate_limit_rps_name():
    args = build_parser().parse_args(["ingest", "--rate-limit-rps", "2.5"])
    assert args.rate_limit_rps == 2.5
