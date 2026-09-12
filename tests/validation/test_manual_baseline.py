from __future__ import annotations

import csv

import pytest

from thirteenf.validation.manual_baseline import verify_manual_baseline


FIELDS = (
    "transition_id",
    "manager_id",
    "human_result",
    "reviewer",
    "review_date",
    "methodology_version",
    "effective_version",
    "reviewer_notes",
)


def _write(path, *, result="MATCH", version="0.1.0", managers=5):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for index in range(30):
            writer.writerow(
                {
                    "transition_id": f"T{index:03d}",
                    "manager_id": str(index % managers + 1),
                    "human_result": result,
                    "reviewer": "Human Reviewer",
                    "review_date": "2026-09-05",
                    "methodology_version": version,
                    "effective_version": "v3",
                    "reviewer_notes": "checked",
                }
            )


def test_valid_manual_baseline_passes(tmp_path):
    path = tmp_path / "review.csv"
    _write(path)
    result = verify_manual_baseline(path, "0.1.0", "v3")
    assert result.passed
    assert result.transition_count == 30
    assert result.manager_count == 5


@pytest.mark.parametrize(
    ("human_result", "version", "managers"),
    [("", "0.1.0", 5), ("MISMATCH", "0.1.0", 5), ("MATCH", "old", 5), ("MATCH", "0.1.0", 4)],
)
def test_incomplete_or_mismatched_manual_baseline_blocks(
    tmp_path, human_result, version, managers
):
    path = tmp_path / "review.csv"
    _write(path, result=human_result, version=version, managers=managers)
    assert not verify_manual_baseline(path, "0.1.0", "v3").passed


def test_manual_baseline_must_match_current_transition_identities(tmp_path):
    path = tmp_path / "review.csv"
    _write(path)
    expected = {f"T{index:03d}" for index in range(29)} | {"CURRENT"}
    result = verify_manual_baseline(
        path,
        "0.1.0",
        "v3",
        expected_transition_ids=expected,
    )
    assert not result.passed
    assert any("identities" in error for error in result.errors)
