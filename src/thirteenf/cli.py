"""Command-line entrypoint for 13F ingestion."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from thirteenf.filings import (
    download_filing,
    parse_submissions,
    latest_n_quarters,
)
from thirteenf.sec_client import SecClient, SecError

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

