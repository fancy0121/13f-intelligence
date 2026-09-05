"""Fail-closed verification of the human Gate 2 review baseline."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class ManualBaselineResult:
    passed: bool
    transition_count: int
    manager_count: int
    errors: tuple[str, ...]


_REQUIRED_FIELDS = {
    "transition_id",
    "manager_id",
    "human_result",
    "reviewer",
    "review_date",
    "methodology_version",
    "effective_version",
}


def verify_manual_baseline(
    path: Path | str,
    methodology_version: str,
    effective_version: str,
    *,
    min_transitions: int = 30,
    min_managers: int = 5,
    expected_transition_ids: set[str] | None = None,
) -> ManualBaselineResult:
    """Validate a completed human review packet without inferring approval."""

    source = Path(path)
    errors: list[str] = []
    if not source.is_file():
        return ManualBaselineResult(False, 0, 0, ("review file is missing",))

    try:
        with source.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing = sorted(_REQUIRED_FIELDS - fields)
            if missing:
                return ManualBaselineResult(
                    False,
                    0,
                    0,
                    (f"missing required columns: {', '.join(missing)}",),
                )
            rows = list(reader)
    except (OSError, csv.Error, UnicodeError) as exc:
        return ManualBaselineResult(False, 0, 0, (f"cannot read review file: {exc}",))

    transition_ids: set[str] = set()
    managers: set[str] = set()
    for ordinal, row in enumerate(rows, start=2):
        transition_id = (row.get("transition_id") or "").strip()
        manager_id = (row.get("manager_id") or "").strip()
        human_result = (row.get("human_result") or "").strip()
        reviewer = (row.get("reviewer") or "").strip()
        review_date = (row.get("review_date") or "").strip()
        row_methodology = (row.get("methodology_version") or "").strip()
        row_effective = (row.get("effective_version") or "").strip()

        if not transition_id:
            errors.append(f"row {ordinal}: transition_id is blank")
        elif transition_id in transition_ids:
            errors.append(f"row {ordinal}: duplicate transition_id {transition_id}")
        else:
            transition_ids.add(transition_id)
        if not manager_id:
            errors.append(f"row {ordinal}: manager_id is blank")
        else:
            managers.add(manager_id)
        if human_result != "MATCH":
            errors.append(f"row {ordinal}: human_result must be MATCH")
        if not reviewer:
            errors.append(f"row {ordinal}: reviewer is blank")
        try:
            date.fromisoformat(review_date)
        except ValueError:
            errors.append(f"row {ordinal}: review_date must be ISO YYYY-MM-DD")
        if row_methodology != methodology_version:
            errors.append(
                f"row {ordinal}: methodology_version does not match "
                f"{methodology_version}"
            )
        if row_effective != effective_version:
            errors.append(
                f"row {ordinal}: effective_version does not match "
                f"{effective_version}"
            )

    transition_count = len(transition_ids)
    manager_count = len(managers)
    if transition_count < min_transitions:
        errors.append(
            f"requires at least {min_transitions} unique transitions; "
            f"found {transition_count}"
        )
    if manager_count < min_managers:
        errors.append(
            f"requires at least {min_managers} managers; found {manager_count}"
        )
    if expected_transition_ids is not None and transition_ids != expected_transition_ids:
        missing = len(expected_transition_ids - transition_ids)
        unexpected = len(transition_ids - expected_transition_ids)
        errors.append(
            "review transition identities do not match the current packet "
            f"(missing={missing}, unexpected={unexpected})"
        )
    return ManualBaselineResult(
        passed=not errors,
        transition_count=transition_count,
        manager_count=manager_count,
        errors=tuple(errors),
    )
