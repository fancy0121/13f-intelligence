"""Command-line entrypoint for 13F ingestion."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from thirteenf.database import connect, init_db
from thirteenf.filings import (
    discover_filings,
    download_filing,
)
from thirteenf.normalization import normalize_raw_tree
from thirteenf.sec_client import (
    SecClient,
    SecError,
    validate_release_user_agent,
)
from thirteenf.changes import (
    compute_portfolio_weights,
    compute_position_changes,
)
from thirteenf.quality import run_all as run_quality_checks
from thirteenf.manager_scoring import (
    apply_scoring,
    manager_counts,
)
from thirteenf.consensus import compute_consensus
from thirteenf.trends import compute_trends
from thirteenf.portfolio import cross_check

ROOT = Path(__file__).resolve().parents[2]


def load_verified_managers(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(
            (line for line in fh if not line.lstrip().startswith("#"))
        )
        for row in reader:
            status = (row.get("validation_status") or "").strip()
            # VERIFIED_WITH_SCOPE has a tracked filing entity (CIK present)
            # and is eligible for ingestion; EXCLUDED / REQUIRES_REVIEW are not.
            if status in ("VERIFIED", "VERIFIED_WITH_SCOPE"):
                rows.append(row)
    return rows


def cmd_ingest(args: argparse.Namespace) -> int:
    managers_path = Path(args.managers)
    raw_root = Path(args.raw_root)
    raw_root.mkdir(parents=True, exist_ok=True)
    user_agent = args.ua or os.getenv("SEC_USER_AGENT")
    if args.release_mode:
        try:
            user_agent = validate_release_user_agent(user_agent or "")
        except ValueError as exc:
            print(f"release ingestion blocked: {exc}")
            return 1
    client = SecClient(
        user_agent=user_agent,
        rate_limit_rps=args.rate_limit_rps,
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
            records = discover_filings(client, cik, quarters=args.quarters)
        except SecError as exc:
            print(f"  [FAIL] {label} submissions: {exc}")
            failures += 1
            continue
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
    """Rebuild a complete SQLite database from validated local raw evidence."""

    summary = normalize_raw_tree(
        Path(args.raw_root),
        Path(args.db_path),
        managers_path=Path(args.managers),
        mappings_path=Path(args.mappings),
        scoring_path=Path(args.scoring),
        methodology_version=args.methodology,
    )
    print(
        f"processed={summary.processed} failed={summary.failed} "
        f"pending_amendments={summary.pending_amendments} "
        f"skipped={summary.skipped} promoted={int(summary.promoted)}"
    )
    for error in summary.errors:
        print(f"  [FAIL] {error}")
    print(f"db={args.db_path}")
    return 0 if summary.promoted else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    """Run deterministic analytics over the normalized DB (offline)."""
    db_path = Path(args.db_path)
    methodology = args.methodology
    conn = connect(db_path)
    init_db(conn)

    weighted = compute_portfolio_weights(conn)
    changes = compute_position_changes(conn, methodology)
    consensus = compute_consensus(
        conn,
        methodology_version=methodology,
        change_scale_divisor=float(args.change_scale_divisor),
        significance_mode=args.significance_mode,
    )
    trends = compute_trends(
        conn,
        methodology_version=methodology,
        stable_abs_threshold=float(args.stable_abs_threshold),
    )
    quality = run_quality_checks(conn, methodology)
    blocked = conn.execute(
        """
        SELECT COUNT(*) FROM effective_periods
        WHERE methodology_version=? AND status!='READY'
        """,
        (methodology,),
    ).fetchone()[0]

    conn.close()
    print(f"portfolio_weight_rows={weighted}")
    print(f"position_changes={changes}")
    print(f"consensus_rows={consensus}")
    print(f"trend_rows={trends}")
    print(f"quality={quality}")
    print(f"blocked_effective_periods={blocked}")
    return 1 if blocked else 0


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


def cmd_portfolio(args: argparse.Namespace) -> int:
    """Cross-check My Portfolio config against the DB (offline)."""
    db_path = Path(args.db_path)
    portfolio_path = Path(args.portfolio)
    conn = connect(db_path)
    init_db(conn)
    results = cross_check(conn, portfolio_path)
    conn.close()
    print(f"portfolio_holdings={len(results)}")
    for r in results:
        print(
            f"{r.ticker}: holders={r.tracked_holders} "
            f"highq={r.high_quality_holders} consensus={r.consensus_score} "
            f"1Q={r.trend_1q} 4Q={r.trend_4q} 8Q={r.trend_8q} "
            f"new={r.notable_new} exit={r.notable_exit} evidence={r.evidence}"
        )
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
    ingest.add_argument("--rate-limit-rps", type=float, default=None)
    ingest.add_argument("--max-retries", type=int, default=5)
    ingest.add_argument("--release-mode", action="store_true")
    ingest.set_defaults(func=cmd_ingest)

    normalize = sub.add_parser(
        "normalize", help="Build SQLite DB from raw cache (offline)"
    )
    normalize.add_argument("--managers", default=str(ROOT / "config" / "managers.csv"))
    normalize.add_argument("--mappings", default=str(ROOT / "config" / "ticker_mappings.csv"))
    normalize.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    normalize.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    normalize.add_argument("--scoring", default=str(ROOT / "config" / "manager_scoring.yaml"))
    normalize.add_argument("--methodology", default="0.1.0")
    normalize.add_argument("--clean", action="store_true")
    normalize.set_defaults(func=cmd_normalize)

    rebuild = sub.add_parser(
        "rebuild", help="Rebuild SQLite DB from raw cache (clean + normalize)"
    )
    rebuild.add_argument("--managers", default=str(ROOT / "config" / "managers.csv"))
    rebuild.add_argument("--mappings", default=str(ROOT / "config" / "ticker_mappings.csv"))
    rebuild.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    rebuild.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    rebuild.add_argument("--scoring", default=str(ROOT / "config" / "manager_scoring.yaml"))
    rebuild.add_argument("--methodology", default="0.1.0")
    rebuild.set_defaults(clean=True)
    rebuild.set_defaults(func=cmd_normalize)

    analyze = sub.add_parser(
        "analyze", help="Compute weights, position changes, and quality checks"
    )
    analyze.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    analyze.add_argument("--methodology", default="0.1.0")
    analyze.add_argument("--change-scale-divisor", default="0.5")
    analyze.add_argument("--significance-mode", default="min_prev_now")
    analyze.add_argument("--stable-abs-threshold", default="0.1")
    analyze.set_defaults(func=cmd_analyze)

    score = sub.add_parser(
        "score", help="Apply governed manager scoring (NOT_APPROVED by default)"
    )
    score.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    score.add_argument("--scoring", default=str(ROOT / "config" / "manager_scoring.yaml"))
    score.add_argument("--methodology", default="0.1.0")
    score.set_defaults(func=cmd_score)

    portfolio = sub.add_parser(
        "portfolio", help="Cross-check My Portfolio against the database"
    )
    portfolio.add_argument("--db-path", default=str(ROOT / "data" / "thirteenf.db"))
    portfolio.add_argument("--portfolio", default=str(ROOT / "config" / "portfolio.csv"))
    portfolio.set_defaults(func=cmd_portfolio)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
