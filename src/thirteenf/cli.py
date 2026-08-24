"""Command-line entrypoint for 13F ingestion."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from thirteenf.database import (
    add_quality_event,
    backfill_holding_tickers,
    bulk_ensure_securities,
    connect,
    init_db,
    replace_holdings,
    upsert_filing,
    upsert_manager,
)
from thirteenf.filings import (
    download_filing,
    parse_submissions,
    latest_n_quarters,
)
from thirteenf.parser import XmlParseError, parse_info_table
from thirteenf.sec_client import SecClient, SecError
from thirteenf.security_master import load_mappings, resolve
from thirteenf.changes import (
    compute_portfolio_weights,
    compute_position_changes,
)
from thirteenf.quality import run_all as run_quality_checks
from thirteenf.manager_scoring import (
    apply_scoring,
    manager_counts,
)

ROOT = Path(__file__).resolve().parents[2]


def load_verified_managers(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            if (row.get("validation_status") or "").strip() == "VERIFIED":
                rows.append(row)
    return rows


def cmd_ingest(args: argparse.Namespace) -> int:
    managers_path = Path(args.managers)
    raw_root = Path(args.raw_root)
    raw_root.mkdir(parents=True, exist_ok=True)
    client = SecClient(
        user_agent=args.ua,
        rate_limit_s=args.rate_limit_s,
        max_retries=args.max_retries,
    )
    managers = load_verified_managers(managers_path)
    print(f"verified_managers={len(managers)}")
    total_files = 0
    failures = 0
    for m in managers:
        cik = int(m["cik"])
        label = m["label"]
        try:
            payload = client.fetch_json(client.submissions_url(cik))
        except SecError as exc:
            print(f"  [FAIL] {label} submissions: {exc}")
            failures += 1
            continue
        records = parse_submissions(cik, payload)
        records = latest_n_quarters(records, n=args.quarters)
        print(f"  [{label}] cik={cik} filings={len(records)}")
        for rec in records:
            try:
                raw = download_filing(client, rec, raw_root, force=args.force)
                if raw.raw_path.exists():
                    total_files += 1
            except SecError as exc:
                print(f"    [FAIL] {rec.accession_number}: {exc}")
                failures += 1
    print(f"raw_files={total_files} failures={failures}")
    return 1 if failures else 0


def cmd_normalize(args: argparse.Namespace) -> int:
    """Build / refresh SQLite DB from raw cache (no network)."""
    raw_root = Path(args.raw_root)
    db_path = Path(args.db_path)
    managers_path = Path(args.managers)
    mappings_path = Path(args.mappings)
    if db_path.exists() and args.clean:
        db_path.unlink()

    conn = connect(db_path)
    init_db(conn)
    mappings = load_mappings(mappings_path)
    mapping_date = datetime.now(timezone.utc).date().isoformat()

    verified = {
        int(row["cik"]): row
        for row in load_verified_managers(managers_path)
    }
    print(f"verified_managers={len(verified)}")

    stats = {
        "filings": 0,
        "holdings": 0,
        "amended": 0,
        "unresolved_cusips": 0,
        "malformed": 0,
        "no_info_table": 0,
        "failed_ingest": 0,
    }

    manager_ids: dict[int, int] = {}
    for cik, row in verified.items():
        mid = upsert_manager(
            conn,
            name=row.get("official_filer_name") or row["label"],
            cik=cik,
            notes=row.get("notes") or "",
        )
        manager_ids[cik] = mid

    for cik in sorted(verified):
        cik_dir = raw_root / str(cik)
        if not cik_dir.exists():
            continue
        for accession_dir in sorted(cik_dir.iterdir()):
            manifest_path = accession_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            mid = manager_ids[int(manifest.get("cik", cik))]
            raw_path = accession_dir / "info_table.xml"
            status = manifest.get("status", "")
            if status == "NO_INFO_TABLE":
                stats["no_info_table"] += 1
                add_quality_event(
                    conn,
                    event_type="FAILED_INGESTION",
                    severity="ERROR",
                    message=f"no info table: {manifest.get('accession')}",
                    manager_id=mid,
                    report_period=manifest.get("report_date"),
                )
                continue
            if status == "FAILED":
                stats["failed_ingest"] += 1
                add_quality_event(
                    conn,
                    event_type="FAILED_INGESTION",
                    severity="ERROR",
                    message=(
                        f"download failed: {manifest.get('accession')} "
                        f"{manifest.get('error', '')}"
                    ),
                    manager_id=mid,
                    report_period=manifest.get("report_date"),
                )
                continue
            if status != "OK" or not raw_path.exists():
                continue

            try:
                rows = parse_info_table(raw_path.read_bytes())
            except XmlParseError as exc:
                stats["malformed"] += 1
                add_quality_event(
                    conn,
                    event_type="MALFORMED_FILING",
                    severity="ERROR",
                    message=f"{manifest.get('accession')}: {exc}",
                    manager_id=mid,
                    report_period=manifest.get("report_date"),
                )
                continue

            is_amendment = (manifest.get("form_type") or "") == "13F-HR/A"
            fid = upsert_filing(
                conn,
                manager_id=mid,
                report_period=manifest.get("report_date") or "",
                filing_date=manifest.get("filing_date") or "",
                accession_number=manifest.get("accession") or "",
                form_type=manifest.get("form_type") or "",
                is_amendment=is_amendment,
                source_url=manifest.get("source_url") or "",
                raw_checksum=manifest.get("checksum") or "",
                raw_path=str(raw_path),
                fetched_at_utc=manifest.get("fetched_at_utc"),
                ingest_status="OK",
            )
            if is_amendment:
                stats["amended"] += 1

            replace_holdings(
                conn,
                filing_id=fid,
                manager_id=mid,
                report_period=manifest.get("report_date") or "",
                rows=rows,
                commit=False,
            )
            stats["holdings"] += len(rows)
            stats["filings"] += 1

            # Resolve securities + assign tickers (deterministic, no guessing).
            security_rows: list[tuple] = []
            unresolved_cusips: set[str] = set()
            for row in rows:
                if not row.cusip:
                    continue
                mapping = resolve(mappings, row.cusip)
                security_rows.append(
                    (
                        mapping.cusip,
                        mapping.ticker,
                        mapping.issuer or (row.name_of_issuer or None),
                        mapping.share_class or (row.title_of_class or None),
                        mapping.mapping_status,
                        mapping.mapping_source,
                    )
                )
                if mapping.mapping_status == "UNRESOLVED":
                    unresolved_cusips.add(mapping.cusip)
            bulk_ensure_securities(
                conn,
                security_rows,
                mapping_date=mapping_date,
                commit=False,
            )
            backfill_holding_tickers(conn, filing_id=fid, commit=False)
            if unresolved_cusips:
                stats["unresolved_cusips"] += len(unresolved_cusips)
                add_quality_event(
                    conn,
                    event_type="UNRESOLVED_CUSIP",
                    severity="WARN",
                    message=(
                        f"{len(unresolved_cusips)} unresolved CUSIPs: "
                        + ", ".join(sorted(unresolved_cusips)[:20])
                    ),
                    manager_id=mid,
                    report_period=manifest.get("report_date"),
                    filing_id=fid,
                    commit=False,
                )
            conn.commit()

    conn.close()
    print(f"stats={stats}")
    print(f"db={db_path}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Run deterministic analytics over the normalized DB (offline)."""
    db_path = Path(args.db_path)
    methodology = args.methodology
    conn = connect(db_path)
    init_db(conn)

    weighted = compute_portfolio_weights(conn)
    changes = compute_position_changes(conn, methodology)
    quality = run_quality_checks(conn, methodology)

    conn.close()
    print(f"portfolio_weight_rows={weighted}")
    print(f"position_changes={changes}")
    print(f"quality={quality}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    """Apply the governed manager scoring file (offline)."""
    db_path = Path(args.db_path)
    scoring_path = Path(args.scoring)
    conn = connect(db_path)
    init_db(conn)
    result = apply_scoring(
        conn,
        scoring_path,
        methodology_version=args.methodology,
    )
    counts = manager_counts(conn)
    conn.close()
    print(f"scoring={result}")
    print(f"manager_status={counts}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thirteenf")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Download raw 13F filings from SEC")
    ingest.add_argument("--managers", default=str(ROOT / "config" / "managers.csv"))
    ingest.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    ingest.add_argument("--quarters", type=int, default=12)
    ingest.add_argument("--force", action="store_true")
    ingest.add_argument("--ua", default=None)
    ingest.add_argument("--rate-limit-s", type=float, default=5.0)
    ingest.add_argument("--max-retries", type=int, default=5)
    ingest.set_defaults(func=cmd_ingest)

    normalize = sub.add_parser(
        "normalize", help="Build SQLite DB from raw cache (offline)"
    )
    normalize.add_argument("--managers", default=str(ROOT / "config" / "managers.csv"))
    normalize.add_argument("--mappings", default=str(ROOT / "config" / "ticker_mappings.csv"))
    normalize.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    normalize.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    normalize.add_argument("--clean", action="store_true")
    normalize.set_defaults(func=cmd_normalize)

    rebuild = sub.add_parser(
        "rebuild", help="Rebuild SQLite DB from raw cache (clean + normalize)"
    )
    rebuild.add_argument("--managers", default=str(ROOT / "config" / "managers.csv"))
    rebuild.add_argument("--mappings", default=str(ROOT / "config" / "ticker_mappings.csv"))
    rebuild.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    rebuild.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    rebuild.set_defaults(func=cmd_normalize)

    analyze = sub.add_parser(
        "analyze", help="Compute weights, position changes, and quality checks"
    )
    analyze.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    analyze.add_argument("--methodology", default="0.1.0")
    analyze.set_defaults(func=cmd_analyze)

    score = sub.add_parser(
        "score", help="Apply governed manager scoring (NOT_APPROVED by default)"
    )
    score.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    score.add_argument("--scoring", default=str(ROOT / "config" / "manager_scoring.yaml"))
    score.add_argument("--methodology", default="0.1.0")
    score.set_defaults(func=cmd_score)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
