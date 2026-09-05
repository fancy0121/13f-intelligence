"""Fail-closed SEC refresh and atomic local release-database rebuild."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "thirteenf.db"
RAW_ROOT = ROOT / "data" / "raw"
STATUS_PATH = ROOT / "data" / "last_update.json"
LOG_PATH = ROOT / "data" / "last_update.log"


def _run(step: str, args: list[str]) -> tuple[int, str]:
    process = subprocess.run(
        [sys.executable, "-m", "thirteenf.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (process.stdout or "") + (process.stderr or "")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n===== {step} ({datetime.now(timezone.utc).isoformat()}) =====\n"
        )
        handle.write(output)
        handle.write(f"\n[exit {process.returncode}]\n")
    if process.returncode != 0:
        print(f"[{step}] exited {process.returncode}; output tail:")
        print(output[-4000:])
    return process.returncode, output


def _parse_int(output: str, key: str) -> int | None:
    needle = key + "="
    for line in output.splitlines():
        if needle not in line:
            continue
        for token in line.split():
            if token.startswith(needle):
                try:
                    return int(token.split("=", 1)[1].strip())
                except ValueError:
                    return None
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--normalize-only", action="store_true")
    parser.add_argument("--release-mode", action="store_true")
    parser.add_argument("--rate-limit-rps", type=float)
    parser.add_argument("--raw-root", default=str(RAW_ROOT))
    parser.add_argument("--db", default=None)
    return parser


def _database_counts(db_path: Path) -> tuple[int | None, int | None]:
    try:
        connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        filings = connection.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
        holdings = connection.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
        connection.close()
        return int(filings), int(holdings)
    except (OSError, sqlite3.Error):
        return None, None


def _write_status(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv if argv is not None else sys.argv[1:])
    except SystemExit as exc:
        return int(exc.code)

    db_path = Path(args.db) if args.db else Path(DB)
    raw_root = Path(args.raw_root)
    normalize_only = bool(args.normalize_only or args.check)
    started = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []
    warnings: list[str] = []
    raw_files = None
    processed = None

    if not normalize_only:
        ingest_args = [
            "ingest",
            "--managers",
            str(ROOT / "config" / "managers.csv"),
            "--raw-root",
            str(raw_root),
        ]
        if args.rate_limit_rps is not None:
            ingest_args.extend(["--rate-limit-rps", str(args.rate_limit_rps)])
        if args.release_mode:
            ingest_args.append("--release-mode")
        code, output = _run("ingest", ingest_args)
        raw_files = _parse_int(output, "raw_files")
        failures = _parse_int(output, "failures")
        changed_failures = _parse_int(output, "changed_failures") or 0
        if code != 0:
            errors.append(f"ingest failed (exit {code})")
        if failures is None:
            errors.append("ingest did not emit a complete failure count")
        elif failures > 0:
            errors.append(f"ingest reported failures={failures}")
        if changed_failures > 0:
            errors.append(f"changed filing failures={changed_failures}")

    if not errors:
        normalize_args = [
            "normalize",
            "--raw-root",
            str(raw_root),
            "--db-path",
            str(db_path),
            "--managers",
            str(ROOT / "config" / "managers.csv"),
            "--mappings",
            str(ROOT / "config" / "ticker_mappings.csv"),
            "--scoring",
            str(ROOT / "config" / "manager_scoring.yaml"),
        ]
        code, output = _run("normalize", normalize_args)
        processed = _parse_int(output, "processed")
        failed = _parse_int(output, "failed")
        pending = _parse_int(output, "pending_amendments")
        promoted = _parse_int(output, "promoted")
        if code != 0:
            errors.append(f"normalize failed (exit {code})")
        if processed is None or failed is None or pending is None or promoted is None:
            errors.append("normalize did not emit complete terminal statistics")
        else:
            if failed > 0:
                errors.append(f"normalize reported failures={failed}")
            if pending > 0:
                errors.append(f"pending amendments={pending}")
            if promoted != 1:
                errors.append("staging database was not promoted")

    filings_count, holdings_count = _database_counts(db_path)
    success = not errors
    releaseable = bool(success and args.release_mode)
    if success and not args.release_mode:
        warnings.append("NOT_RELEASEABLE: run did not use --release-mode")
    status = {
        "last_update_started_at": started,
        "last_update_finished_at": datetime.now(timezone.utc).isoformat(),
        "source": "normalize_only" if normalize_only else "full",
        "success": success,
        "releaseable": releaseable,
        "raw_files": raw_files,
        "filings_processed": processed if processed is not None else filings_count,
        "holdings_processed": holdings_count,
        "errors": errors,
        "warnings": warnings,
        "log_path": str(LOG_PATH),
    }
    _write_status(status)

    if success:
        label = "RELEASEABLE" if releaseable else "NOT_RELEASEABLE"
        print(
            f"Update OK [{label}]. filings={status['filings_processed']} "
            f"holdings={holdings_count} raw_files={raw_files}"
        )
        print(f"Status artifact: {STATUS_PATH}")
        print(f"Log: {LOG_PATH}")
        return 0
    print("Update failed. Existing dashboard database was not replaced.")
    print(f"See log: {LOG_PATH}")
    for error in errors:
        print(" -", error)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
