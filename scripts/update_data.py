"""One-click data update orchestrator (v0.5.1).

Reuses the EXISTING approved pipeline only:
  python -m thirteenf ingest     (SEC download -> raw cache)
  python -m thirteenf normalize  (raw -> SQLite, idempotent)
  python -m thirteenf analyze    (weights + position changes + quality)

Writes data/last_update.json (status artifact) and data/last_update.log.
Does NOT run predictive research. On failure, leaves the existing DB intact.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "thirteenf.db"
STATUS_PATH = ROOT / "data" / "last_update.json"
LOG_PATH = ROOT / "data" / "last_update.log"


def _run(step: str, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "thirteenf.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(f"\n===== {step} ({datetime.now(timezone.utc).isoformat()}) =====\n")
        fh.write(output)
        fh.write(f"\n[exit {proc.returncode}]\n")
    return proc.returncode, output


def _parse_int(output: str, key: str) -> int | None:
    for line in output.splitlines():
        if line.startswith(key + "="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    check_only = "--check" in argv
    rate_limit = 5.0
    if "--rate-limit" in argv:
        try:
            rate_limit = float(argv[argv.index("--rate-limit") + 1])
        except (IndexError, ValueError):
            rate_limit = 5.0
    started = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    # 1. ingest (network) unless --check
    raw_files_added = None
    if not check_only:
        code, out = _run(
            "ingest",
            [
                "ingest", "--managers", str(ROOT / "config" / "managers.csv"),
                "--rate-limit-s", str(rate_limit),
            ],
        )
        raw_files_added = _parse_int(out, "raw_files")
        failures = _parse_int(out, "failures")
        if code != 0 or (failures and failures > 0):
            errors.append(f"ingest failed (exit {code}, failures={failures})")

    # 2. normalize (offline, idempotent)
    code, out = _run("normalize", ["normalize", "--db-path", str(DB)])
    filings = _parse_int(out, "filings")
    if code != 0:
        errors.append(f"normalize failed (exit {code})")

    # 3. analyze (offline, idempotent)
    code, out = _run("analyze", ["analyze", "--db-path", str(DB)])
    if code != 0:
        errors.append(f"analyze failed (exit {code})")

    # filings + holdings processed (from DB counts)
    filings_count = None
    holdings = None
    try:
        import sqlite3

        con = sqlite3.connect(DB)
        filings_count = con.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
        holdings = con.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
        con.close()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"status read failed: {exc}")

    success = not errors
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = {
        "last_update_started_at": started,
        "last_update_finished_at": datetime.now(timezone.utc).isoformat(),
        "source": "check" if check_only else "full",
        "success": success,
        "raw_files_added": raw_files_added,
        "filings_processed": filings if filings is not None else filings_count,
        "holdings_processed": holdings,
        "errors": errors,
        "log_path": str(LOG_PATH),
    }
    STATUS_PATH.write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if success:
        print(f"Update OK. filings={filings} holdings={holdings} raw_added={raw_files_added}")
        print(f"Status artifact: {STATUS_PATH}")
        print(f"Log: {LOG_PATH}")
        return 0
    print("Update failed. Existing dashboard data remains available.")
    print(f"See log: {LOG_PATH}")
    for e in errors:
        print(" -", e)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
