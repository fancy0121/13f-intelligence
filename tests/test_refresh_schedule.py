"""Calendar and orchestration tests; no SEC requests or production writes."""
import importlib.util
import contextlib
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("refresh_schedule", ROOT / "scripts/refresh_schedule.py")
schedule = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schedule)


class CalendarTests(unittest.TestCase):
    def test_next_monthly_and_main(self):
        events = schedule.upcoming(date(2026, 10, 23), 6)
        self.assertEqual(events[0]["date"], "2026-11-01")
        self.assertEqual(events[0]["reasons"], ["MONTHLY_AMENDMENTS"])
        self.assertEqual(events[1]["date"], "2026-11-17")
        self.assertEqual(events[1]["reasons"], ["QUARTERLY_MAIN:2026-09-30"])
        self.assertEqual([e["date"] for e in events[2:]],
                         ["2026-11-24", "2026-12-01", "2026-12-08", "2026-12-15"])

    def test_weekend_deadline_is_not_naive_45_days(self):
        self.assertEqual(schedule.reasons(date(2026, 11, 16)), [])
        self.assertIn("QUARTERLY_MAIN:2026-09-30", schedule.reasons(date(2026, 11, 17)))
        self.assertIn("QUARTERLY_MAIN:2026-03-31", schedule.reasons(date(2026, 5, 18)))
        self.assertIn("QUARTERLY_MAIN:2026-12-31", schedule.reasons(date(2027, 2, 17)))

    def test_four_followups_and_overlap_coalescing(self):
        self.assertEqual(schedule.reasons(date(2026, 12, 1)),
                         ["WEEKLY_CATCHUP:2026-09-30:2", "MONTHLY_AMENDMENTS"])
        self.assertEqual(schedule.reasons(date(2026, 12, 22)), [])

    def test_expiry_and_invalid_past_fail_closed(self):
        for day in (date(2025, 12, 31), date(2029, 1, 1)):
            with self.assertRaises(ValueError):
                schedule.reasons(day)

    def test_timezone_is_explicit_utc(self):
        self.assertEqual(schedule.event_time("2026-11-01"), "2026-11-01T14:17:00+00:00")

    def test_all_main_dates_follow_official_deadlines(self):
        self.assertEqual(len(schedule.QUARTERS), 12)
        for period, deadline, main in schedule.QUARTERS:
            deadline, main = date.fromisoformat(deadline), date.fromisoformat(main)
            self.assertGreater(main, deadline)
            self.assertLessEqual((main - deadline).days, 3)
            self.assertLess(main.weekday(), 5)
            self.assertIn("QUARTERLY_MAIN:" + period, schedule.reasons(main))


class RunnerTests(unittest.TestCase):
    def test_historical_date_cannot_execute_network(self):
        with patch.object(schedule, "datetime") as clock, patch.object(schedule.subprocess, "run") as run:
            clock.now.return_value = datetime(2026, 10, 23, tzinfo=timezone.utc)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = schedule.main(["--execute", "--date", "2026-11-17"])
        self.assertEqual(code, 1)
        self.assertIn("EXECUTION_DATE_MUST_BE_TODAY_UTC", output.getvalue())
        run.assert_not_called()

    def test_no_due_day_never_runs(self):
        with patch.object(schedule.subprocess, "run") as run:
            result = schedule.execute(date(2026, 10, 23), ROOT, {})
        run.assert_not_called()
        self.assertEqual(result["state"], "NOT_DUE")

    def test_missing_config_fails_without_network(self):
        with patch.object(schedule.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                schedule.execute(date(2026, 11, 17), ROOT, {})
        run.assert_not_called()

    def test_runner_preserves_candidate_boundary(self):
        # Mock filesystem preconditions, never create/touch a real serving database.
        with patch.object(Path, "is_file", return_value=True):
            root = ROOT
            serving = root / "test-only-not-a-real-serving-database.db"
            receipt = {"state": "CANDIDATE_AWAITING_REVIEW", "releaseable": False,
                       "source": "SEC_REFRESH", "serving_snapshot_unchanged": True}
            env = {"THIRTEENF_SERVING_DB": str(serving), "SEC_USER_AGENT": "Configured contact"}
            with patch.object(schedule.subprocess, "run", return_value=
                              subprocess.CompletedProcess([], 0, json.dumps(receipt), "")) as run:
                result = schedule.execute(date(2026, 11, 17), root, env)
            self.assertEqual(result["state"], "CANDIDATE_AWAITING_REVIEW")
            self.assertFalse(result["releaseable"])
            self.assertNotIn("--offline", run.call_args.args[0])
            for bad in ({**receipt, "releaseable": True}, {**receipt, "source": "OFFLINE_RAW_REBUILD"},
                        {**receipt, "serving_snapshot_unchanged": False}):
                with patch.object(schedule.subprocess, "run", return_value=
                                  subprocess.CompletedProcess([], 0, json.dumps(bad), "")):
                    with self.assertRaises(RuntimeError):
                        schedule.execute(date(2026, 11, 17), root, env)

    def test_child_failure_and_timeout_are_not_success(self):
        with patch.object(Path, "is_file", return_value=True):
            root = ROOT
            serving = root / "test-only-not-a-real-serving-database.db"
            env = {"THIRTEENF_SERVING_DB": str(serving), "SEC_USER_AGENT": "Configured contact"}
            for output in (subprocess.CompletedProcess([], 1, "private error", ""),
                           subprocess.CompletedProcess([], 0, "malformed", "")):
                with patch.object(schedule.subprocess, "run", return_value=output):
                    with self.assertRaises(RuntimeError):
                        schedule.execute(date(2026, 11, 17), root, env)
            with patch.object(schedule.subprocess, "run", side_effect=subprocess.TimeoutExpired("candidate", 3000)):
                with self.assertRaises(RuntimeError):
                    schedule.execute(date(2026, 11, 17), root, env)


class WorkflowContractTests(unittest.TestCase):
    def test_connection_drill_uses_read_only_forced_command(self):
        text = (ROOT / ".github/workflows/refresh-schedule.yml").read_text(encoding="utf-8")
        self.assertIn("options: [inspect, connection-test, run, notification-test]", text)
        self.assertIn("remote_command=inspect", text)
        self.assertIn('"$remote_command"', text)
        self.assertIn("StrictHostKeyChecking=yes", text)
        self.assertNotIn("StrictHostKeyChecking=no", text)


if __name__ == "__main__":
    unittest.main()
