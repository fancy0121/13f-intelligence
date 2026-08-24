"""Phase 0.5 - Manager Universe Validation against SEC EDGAR.

For each product-level candidate label, discover CIK candidates via SEC
browse-edgar company search (13F filter), then fetch the authoritative
submissions JSON to confirm official filer name and 13F activity.

Status outcomes:
  VERIFIED          - exactly one candidate whose official name matches and
                      who has active 13F-HR filing history.
  REQUIRES_REVIEW   - ambiguous (multiple plausible candidates), or name does
                      not clearly match, or 13F history is stale/absent.
  UNRESOLVED        - no candidate found.

This script never guesses a CIK; it reports candidates for human review.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

UA_DEFAULT = "13F Intelligence Research validation@example.com"
SEARCH_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
REGISTRY_URL = "https://www.sec.gov/files/company_tickers.json"

_REGISTRY_CACHE: list[dict] | None = None


def _open(url: str, user_agent: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw


def search_candidates(label: str, user_agent: str, rate_limit_s: float) -> list[dict]:
    """Search SEC browse-edgar for companies matching label, filtered to 13F."""
    query = urllib.parse.quote_plus(label)
    url = (
        f"{SEARCH_URL}?action=getcompany&company={query}"
        f"&type=13F&dateb=&owner=include&count=40&output=atom"
    )
    raw = _open(url, user_agent)
    text = raw.decode("utf-8", "replace")
    # SEC returns two Atom shapes:
    #   1) multi-result list: <id>urn:tag:www.sec.gov:cik=0001234567</id>
    #   2) single-company detail: <company-info><cik>0001234567</cik>...
    # Collect CIKs from both, preserving order and deduplicating.
    ciks = re.findall(r"cik=(\d{10})", text) + re.findall(r"<cik>(\d{10})</cik>", text)
    conformed_names = re.findall(
        r"<conformed-name>([^<]+)</conformed-name>", text
    )
    last_dates = re.findall(r"<last-date>([^<]+)</last-date>", text)
    candidates = []
    for i, cik in enumerate(dict.fromkeys(ciks)):  # dedupe, keep order
        candidates.append(
            {
                "cik": int(cik),
                "search_label": label,
                "conformed_name": conformed_names[i] if i < len(conformed_names) else "",
                "last_date": last_dates[i] if i < len(last_dates) else "",
            }
        )
    time.sleep(rate_limit_s)
    return candidates


def search_terms(label: str, aliases: list[str]) -> list[str]:
    """Deterministic query expansion: aliases first, then progressively shorter
    token prefixes of the label (SEC browse-edgar full-name queries often return
    empty while short queries match). This only affects *search recall*; the
    authoritative identity always comes from submissions JSON + similarity."""
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        term = term.strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            terms.append(term)

    for alias in aliases:
        add(alias)
    tokens = [t for t in re.split(r"\s+", label.strip()) if t]
    for n in range(len(tokens), 1, -1):
        add(" ".join(tokens[:n]))
    return terms


def search_all(
    label: str, aliases: list[str], user_agent: str, rate_limit_s: float
) -> list[dict]:
    """Run browse-edgar search across expanded terms; merge CIKs (dedupe)."""
    merged: dict[int, dict] = {}
    for term in search_terms(label, aliases):
        for cand in search_candidates(term, user_agent, rate_limit_s):
            merged.setdefault(cand["cik"], cand)
    return list(merged.values())


def fetch_submissions(cik: int, user_agent: str, rate_limit_s: float) -> dict:
    raw = _open(SUBMISSIONS_URL.format(cik=cik), user_agent)
    time.sleep(rate_limit_s)
    return json.loads(raw)


def load_registry(user_agent: str) -> list[dict]:
    """SEC official company tickers registry (title -> cik). Not a guess:
    it is an authoritative SEC data file used only to surface candidates."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE
    raw = _open(REGISTRY_URL, user_agent)
    data = json.loads(raw)
    rows = []
    for rec in data.values():
        rows.append(
            {
                "title": rec["title"],
                "ticker": rec["ticker"],
                "cik": int(rec["cik_str"]),
            }
        )
    _REGISTRY_CACHE = rows
    return rows


def registry_candidates(label: str, user_agent: str) -> list[dict]:
    """Surface registry entries whose title tokens are a strong match for the
    label (bidirectional token coverage >= 0.6). Loose one-token matches (e.g.
    generic "Capital" / "Group") are rejected to avoid polluting candidates."""
    label_tokens = name_tokens(label)
    if not label_tokens:
        return []
    out = []
    for rec in load_registry(user_agent):
        title_tokens = name_tokens(rec["title"])
        if not title_tokens:
            continue
        overlap = len(label_tokens & title_tokens)
        label_coverage = overlap / len(label_tokens)
        title_coverage = overlap / len(title_tokens)
        if label_coverage >= 0.6 and title_coverage >= 0.6:
            out.append(
                {
                    "cik": rec["cik"],
                    "search_label": label,
                    "conformed_name": rec["title"],
                    "last_date": "",
                    "registry_ticker": rec["ticker"],
                }
            )
    return out


def name_tokens(name: str) -> set[str]:
    norm = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    tokens = {t for t in norm.split() if t and t not in {"the", "ltd", "llc", "inc", "corp", "co", "lp", "l.p."}}
    return tokens


def name_similarity(product_label: str, official_name: str) -> float:
    """Deterministic token-overlap similarity, 0..1. Not a guess; only a rank."""
    a = name_tokens(product_label)
    b = name_tokens(official_name)
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return overlap / max(len(a), len(b))


def analyze_manager(
    label: str,
    aliases: list[str],
    user_agent: str,
    rate_limit_s: float,
    max_candidates: int,
) -> dict:
    candidates = search_all(label, aliases, user_agent, rate_limit_s)
    # Merge SEC official registry candidates (dedupe by CIK).
    merged: dict[int, dict] = {c["cik"]: c for c in candidates}
    for rc in registry_candidates(label, user_agent):
        merged.setdefault(rc["cik"], rc)
    candidates = list(merged.values())
    rows = []
    # Prefer candidates that have a conformed name resembling the label, then
    # fall back to the raw search order. Still deterministic - no guessing.
    # Pre-fetch ranking: prefer candidates that already have a high-similarity
    # conformed name (single-company search hits / registry), then keep search
    # order. We fetch enough candidates that truncation does not drop the true
    # filer; max_candidates*2 gives margin.
    ranked = sorted(
        candidates[: max_candidates * 3],
        key=lambda c: (
            -(
                name_similarity(label, c["conformed_name"])
                if c["conformed_name"]
                else 0.0
            ),
            c["cik"],
        ),
    )
    seen = set()
    for cand in ranked[:max_candidates]:
        if cand["cik"] in seen:
            continue
        seen.add(cand["cik"])
        try:
            sub = fetch_submissions(cand["cik"], user_agent, rate_limit_s)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "cik": cand["cik"],
                    "official_name": "FETCH_ERROR",
                    "similarity": 0.0,
                    "thirteen_f_count": 0,
                    "thirteen_f_amendments": 0,
                    "first_13f": "",
                    "last_13f": "",
                    "recent_13f": "",
                    "note": str(exc)[:120],
                }
            )
            continue
        official = sub.get("name", "")
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accession = recent.get("accessionNumber", [])
        report_dates = recent.get("reportDate", [])
        thirteen_f = [
            i for i, f in enumerate(forms) if f in ("13F-HR", "13F-HR/A")
        ]
        count_hr = sum(1 for i in thirteen_f if forms[i] == "13F-HR")
        count_a = sum(1 for i in thirteen_f if forms[i] == "13F-HR/A")
        first_13f = dates[thirteen_f[-1]] if thirteen_f else ""
        last_13f = dates[thirteen_f[0]] if thirteen_f else ""
        last_report = report_dates[thirteen_f[0]] if thirteen_f else ""
        rows.append(
            {
                "cik": cand["cik"],
                "official_name": official,
                "registry_ticker": cand.get("registry_ticker", ""),
                "similarity": round(name_similarity(label, official), 3),
                "thirteen_f_count": count_hr + count_a,
                "thirteen_f_amendments": count_a,
                "first_13f": first_13f,
                "last_13f": last_13f,
                "recent_13f": last_report,
                "note": f"latest report period: {last_report or 'N/A'}",
            }
        )
    return {"label": label, "candidates": rows}


def decide_status(analysis: dict, min_recent_period: str) -> str:
    """Classify VERIFIED / REQUIRES_REVIEW / UNRESOLVED deterministically.

    - VERIFIED: exactly one active 13F filer with high name similarity and no
      competing near-similar active entity (entity ambiguity).
    - REQUIRES_REVIEW: multiple candidates, stale 13F, name mismatch, or any
      ambiguity about which SEC entity corresponds to the product label.
    - UNRESOLVED: no candidate found at all.
    """
    cands = [
        c for c in analysis["candidates"] if c["official_name"] != "FETCH_ERROR"
    ]
    if not cands:
        return "UNRESOLVED"
    active = [c for c in cands if c["thirteen_f_count"] > 0]
    strong = [c for c in active if c["similarity"] >= 0.6]
    recent_strong = [c for c in strong if c["recent_13f"] >= min_recent_period]
    if len(recent_strong) == 1:
        cand = recent_strong[0]
        # Competing recent filer with near-similar name => real entity ambiguity.
        competitors = [
            c
            for c in cands
            if c["cik"] != cand["cik"]
            and c["thirteen_f_count"] > 0
            and c["similarity"] >= 0.4
            and c["recent_13f"] >= min_recent_period
        ]
        if competitors:
            return "REQUIRES_REVIEW"
        return "VERIFIED"
    return "REQUIRES_REVIEW"


def best_candidate(analysis: dict, min_recent_period: str = "") -> dict | None:
    """Best candidate for display: prefer recent active 13F filers, then any
    active filer, then similarity. Avoids showing a stale high-similarity
    legacy entity (e.g. an old GP entity) over the current filing entity."""
    cands = [
        c for c in analysis["candidates"] if c["official_name"] != "FETCH_ERROR"
    ]
    if not cands:
        return None
    recent = (
        [c for c in cands if c["recent_13f"] >= min_recent_period]
        if min_recent_period
        else []
    )
    active = [c for c in cands if c["thirteen_f_count"] > 0]
    pool = recent or active or cands
    return max(pool, key=lambda c: (c["similarity"], c["cik"]))


def render_report(results: list[dict], min_recent_period: str) -> str:
    today = date.today().isoformat()
    lines = [
        "# Manager Universe Validation Report",
        "",
        f"> Generated: {today}  |  Method: SEC EDGAR browse-edgar (13F filter) + "
        "submissions JSON (authoritative filer names)",
        f"> Minimum recent report period for VERIFIED: {min_recent_period}",
        "",
        "## Summary",
        "",
        "| Label | Status | Best CIK | Official filer name | Similarity | 13F count | Latest report period |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        best = best_candidate(r, min_recent_period)
        if best:
            lines.append(
                f"| {r['label']} | {r['status']} | {best['cik']:010d} | "
                f"{best['official_name']} | {best['similarity']} | "
                f"{best['thirteen_f_count']} | {best['recent_13f'] or 'N/A'} |"
            )
        else:
            lines.append(f"| {r['label']} | {r['status']} | - | - | - | 0 | N/A |")
    lines += ["", "## Candidate detail", ""]
    for r in results:
        lines.append(f"### {r['label']} — {r['status']}")
        lines.append("")
        if not r["candidates"]:
            lines.append("- No candidates found.")
        for c in r["candidates"]:
            lines.append(
                f"- CIK {c['cik']:010d} | {c['official_name']} | "
                f"ticker={c.get('registry_ticker') or '-'} | "
                f"sim={c['similarity']} | 13F={c['thirteen_f_count']} "
                f"(A={c['thirteen_f_amendments']}) | first={c['first_13f']} "
                f"| last filing={c['last_13f']} | latest report period={c['recent_13f']}"
                f"{' | ' + c['note'] if c.get('note') else ''}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate 30-manager universe against SEC")
    parser.add_argument("--managers", default=str(ROOT / "config" / "managers.csv"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "manager_universe_validation.md"))
    parser.add_argument("--ua", default=UA_DEFAULT)
    parser.add_argument("--rate-limit-s", type=float, default=0.2)
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--min-recent-period", default="2025-12-31")
    args = parser.parse_args()

    labels = []
    with open(args.managers, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            label = (row.get("label") or "").strip()
            if label:
                aliases = [
                    a.strip()
                    for a in (row.get("search_aliases") or "").split(";")
                    if a.strip()
                ]
                labels.append((label, aliases))

    results = []
    for label, aliases in labels:
        print(f"validating: {label}", flush=True)
        analysis = analyze_manager(
            label, aliases, args.ua, args.rate_limit_s, args.max_candidates
        )
        analysis["status"] = decide_status(analysis, args.min_recent_period)
        results.append(analysis)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(results, args.min_recent_period), encoding="utf-8")

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    print(f"status_counts={status_counts}")
    print(f"report={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
