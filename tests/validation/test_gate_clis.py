from __future__ import annotations

import csv
import json
import subprocess
import sys


def test_gate_clis_write_machine_and_human_reports(
    sample_bundle, repo_root, tmp_path
):
    gate1_dir = tmp_path / "gate1"
    gate1 = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "gate1_reconciliation.py"),
            "--db",
            str(sample_bundle.db_path),
            "--raw-root",
            str(sample_bundle.raw_root),
            "--output-dir",
            str(gate1_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert gate1.returncode == 0, gate1.stderr
    assert json.loads((gate1_dir / "gate1.json").read_text(encoding="utf-8"))[
        "status"
    ] == "PASS"
    assert (gate1_dir / "gate1.md").is_file()

    gate2_dir = tmp_path / "gate2"
    packet = tmp_path / "manual-review.csv"
    gate2 = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "gate2_review.py"),
            "--db",
            str(sample_bundle.db_path),
            "--raw-root",
            str(sample_bundle.raw_root),
            "--output-dir",
            str(gate2_dir),
            "--emit-manual-packet",
            str(packet),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert gate2.returncode == 2, gate2.stderr
    payload = json.loads((gate2_dir / "gate2.json").read_text(encoding="utf-8"))
    assert payload["automatic_status"] == "PASS"
    assert payload["human_status"] == "NOT_REVIEWED"
    assert not payload["releaseable"]
    assert (gate2_dir / "gate2.md").is_file()
    with packet.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 30
    assert all(not row["human_result"] and not row["reviewer"] for row in rows)
    assert all("accession_number" in row["raw_provenance"] for row in rows)

    for row in rows:
        row["human_result"] = "MATCH"
        row["reviewer"] = "Synthetic test reviewer"
        row["review_date"] = "2026-09-05"
    reviewed = tmp_path / "reviewed.csv"
    with reviewed.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    approved = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "gate2_review.py"),
            "--db",
            str(sample_bundle.db_path),
            "--raw-root",
            str(sample_bundle.raw_root),
            "--output-dir",
            str(tmp_path / "gate2-reviewed"),
            "--manual-baseline",
            str(reviewed),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert approved.returncode == 0, approved.stderr
