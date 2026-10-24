"""SEC quarterly candidate-refresh calendar. Never approves or deploys data."""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

# SEC FAQ 25, retrieved 2026-10-23. Explicit dates include SEC holiday exceptions.
# https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f
# Tuple = report period, official deadline, next US business day (our main run).
QUARTERS = (
    ("2025-12-31", "2026-02-17", "2026-02-18"),
    ("2026-03-31", "2026-05-15", "2026-05-18"),
    ("2026-06-30", "2026-08-14", "2026-08-17"),
    ("2026-09-30", "2026-11-16", "2026-11-17"),
    ("2026-12-31", "2027-02-16", "2027-02-17"),
    ("2027-03-31", "2027-05-17", "2027-05-18"),
    ("2027-06-30", "2027-08-16", "2027-08-17"),
    ("2027-09-30", "2027-11-15", "2027-11-16"),
    ("2027-12-31", "2028-02-14", "2028-02-15"),
    ("2028-03-31", "2028-05-15", "2028-05-16"),
    ("2028-06-30", "2028-08-14", "2028-08-15"),
    ("2028-09-30", "2028-11-14", "2028-11-15"),
)
VALID_FROM = date(2026, 1, 1)
VALID_UNTIL = date(2028, 12, 31)


def reasons(day: date) -> list[str]:
    if not VALID_FROM <= day <= VALID_UNTIL:
        raise ValueError("CALENDAR_EXPIRED_OR_UNSUPPORTED: review SEC deadlines before continuing")
    result = []
    for period, _, main in QUARTERS:
        delta = (day - date.fromisoformat(main)).days
        if delta == 0:
            result.append(f"QUARTERLY_MAIN:{period}")
        elif delta in (7, 14, 21, 28):
            result.append(f"WEEKLY_CATCHUP:{period}:{delta // 7}")
    if day.day == 1:
        result.append("MONTHLY_AMENDMENTS")
    return result


def event_time(iso_day: str) -> str:
    return datetime.combine(date.fromisoformat(iso_day), time(14, 17), timezone.utc).isoformat()


def upcoming(start: date, count: int = 6) -> list[dict]:
    reasons(start)  # Validate even if count is zero.
    result = []
    day = start
    while len(result) < count and day <= VALID_UNTIL:
        due = reasons(day)
        if due:
            result.append({"date": day.isoformat(), "at_utc": event_time(day.isoformat()), "reasons": due})
        day += timedelta(days=1)
    return result


def execute(day: date, root: Path, env: dict) -> dict:
    """Run only the existing candidate pipeline, never the legacy updater/publisher."""
    due = reasons(day)
    if not due:
        return {"state": "NOT_DUE", "reasons": [], "releaseable": False}
    serving = env.get("THIRTEENF_SERVING_DB")
    if not serving or not Path(serving).is_absolute() or not Path(serving).is_file():
        raise ValueError("CONFIGURATION_REQUIRED: explicit absolute frozen serving database")
    if not env.get("SEC_USER_AGENT", "").strip():
        raise ValueError("CONFIGURATION_REQUIRED: SEC_USER_AGENT on the VPS")
    entry = root / "scripts/refresh_candidate.py"
    if not entry.is_file():
        raise ValueError("CONFIGURATION_REQUIRED: reviewed candidate pipeline must be installed")
    command = [sys.executable, str(entry), "--serving-db", serving,
               "--run-root", str(root / "data/private/updates"), "--raw-root", str(root / "data/raw")]
    # Explicit operator selection, never silently use/expand a source exclusion policy.
    if env.get("THIRTEENF_QUARANTINE_POLICY"):
        command.extend(["--quarantine-policy", env["THIRTEENF_QUARANTINE_POLICY"]])
    try:
        process = subprocess.run(command, cwd=root, env={**os.environ, **env},
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3000)
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError("REFRESH_EXECUTION_FAILED: inspect private VPS receipts") from None
    if process.returncode != 0:
        raise RuntimeError("REFRESH_FAILED: inspect private VPS receipts")
    try:
        receipt = json.loads(process.stdout)
        valid = (receipt["state"] == "CANDIDATE_AWAITING_REVIEW"
                 and receipt["releaseable"] is False
                 and receipt["source"] == "SEC_REFRESH"
                 and receipt["serving_snapshot_unchanged"] is True)
    except (ValueError, TypeError, KeyError):
        valid = False
    if not valid:
        raise RuntimeError("REFRESH_RECEIPT_INVALID: no release or deployment allowed")
    return {"state": "CANDIDATE_AWAITING_REVIEW", "reasons": due,
            "releaseable": False, "deployment_status": "NOT_DEPLOYED"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date(), help="UTC calendar date")
    parser.add_argument("--next", type=int, default=6)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.execute:
            # A historical test date must never trigger real SEC operations.
            if args.date != datetime.now(timezone.utc).date():
                raise ValueError("EXECUTION_DATE_MUST_BE_TODAY_UTC")
            result = execute(args.date, Path(__file__).resolve().parents[1], dict(os.environ))
        else:
            result = {"date": args.date.isoformat(), "due": bool(reasons(args.date)),
                      "reasons": reasons(args.date), "next": upcoming(args.date, args.next),
                      "calendar_valid_until": VALID_UNTIL.isoformat(), "releaseable": False}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"state": "FAILED", "error": str(exc), "releaseable": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
