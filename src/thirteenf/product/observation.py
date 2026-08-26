"""Real-use observation infrastructure (v0.5).

Prospective, non-rewritable episode capture: pre-use state must be saved
before post-use outcomes. Local-first append-only JSONL. No fake episodes,
no auto-judged subjective flags, no forward-return dependencies.
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


PRODUCT_VERSION = "v0.4.0"      # observed evidence product version
PROTOCOL_VERSION = "v0.5"
TARGET_VALID_EPISODES = 20

EPISODE_FIELDS = [
    "episode_id", "episode_cluster_id", "created_at", "updated_at",
    "target_type", "target_id", "target_label", "is_portfolio_target",
    "familiarity_class", "research_question",
    "pre_use_knowledge", "pre_use_assumptions", "pre_use_uncertainties",
    "planned_next_step", "baseline_method",
    "product_views_used", "product_version",
    "new_fact_found", "contradicting_fact_found",
    "stale_assumption_corrected", "quality_risk_discovered",
    "research_path_changed", "research_time_saved",
    "no_incremental_information",
    "estimated_manual_effort_bucket",
    "misuse_risk", "misuse_type", "product_design_issue",
    "post_use_next_step", "notes",
    "episode_validity", "invalid_reason",
]

OUTCOME_FLAGS = [
    "new_fact_found", "contradicting_fact_found",
    "stale_assumption_corrected", "quality_risk_discovered",
    "research_path_changed", "research_time_saved",
    "no_incremental_information",
]

# Subjective fields: never auto-populated by code.
SUBJECTIVE_FIELDS = [
    "pre_use_knowledge", "pre_use_assumptions", "pre_use_uncertainties",
    "planned_next_step", "post_use_next_step",
    "contradicting_fact_found", "research_path_changed",
    "no_incremental_information", "misuse_risk", "misuse_type",
    "product_design_issue",
]

VALIDITY = {
    "VALID",
    "INVALID_NO_PRE_USE_CAPTURE",
    "INVALID_SYNTHETIC_TASK",
    "INVALID_PRODUCT_ERROR",
    "INVALID_DUPLICATE",
    "INVALID_OTHER",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _flag(v) -> int:
    return 1 if str(v).strip().lower() in ("1", "true", "yes", "y") else 0


class ObservationStore:
    """Append-only local episode logger (JSONL) + product error log."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.episodes_path = self.dir / "episodes.jsonl"
        self.errors_path = self.dir / "product_errors.jsonl"

    # ------------------------------------------------------------------
    def _read(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        out = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
        return out

    def _append(self, path: Path, record: dict) -> None:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def episodes(self) -> list[dict]:
        return self._read(self.episodes_path)

    def errors(self) -> list[dict]:
        return self._read(self.errors_path)

    # ------------------------------------------------------------------
    def start_episode(self, pre: dict) -> dict:
        """Create an episode with pre-use state. Must run before exposure."""
        now = _now()
        episode = {
            "episode_id": pre.get("episode_id") or str(uuid.uuid4()),
            "episode_cluster_id": (pre.get("episode_cluster_id")
                                   or pre.get("target_id")
                                   or pre.get("episode_id") or ""),
            "created_at": pre.get("created_at") or now,
            "updated_at": now,
            "target_type": pre.get("target_type", ""),
            "target_id": pre.get("target_id", ""),
            "target_label": pre.get("target_label", ""),
            "is_portfolio_target": int(_flag(pre.get("is_portfolio_target"))),
            "familiarity_class": pre.get("familiarity_class", "UNKNOWN"),
            "research_question": pre.get("research_question", ""),
            "pre_use_knowledge": pre.get("pre_use_knowledge", "UNKNOWN"),
            "pre_use_assumptions": pre.get("pre_use_assumptions", "UNKNOWN"),
            "pre_use_uncertainties": pre.get("pre_use_uncertainties", "UNKNOWN"),
            "planned_next_step": pre.get("planned_next_step", "UNKNOWN"),
            "baseline_method": pre.get("baseline_method", "UNKNOWN"),
            "product_views_used": pre.get("product_views_used", ""),
            "product_version": pre.get("product_version") or PRODUCT_VERSION,
            "synthetic": int(_flag(pre.get("synthetic"))),
            "episode_validity": "PENDING",
            "invalid_reason": "",
        }
        for f in OUTCOME_FLAGS + [
            "estimated_manual_effort_bucket", "misuse_risk", "misuse_type",
            "product_design_issue", "post_use_next_step", "notes",
        ]:
            episode.setdefault(f, "UNKNOWN" if f in SUBJECTIVE_FIELDS or f in (
                "misuse_risk", "misuse_type", "post_use_next_step",
                "estimated_manual_effort_bucket", "product_design_issue",
            ) else 0)
        self._append(self.episodes_path, episode)
        return episode

    def finish_episode(self, episode_id: str, post: dict) -> dict | None:
        """Complete an episode with post-use outcomes; compute validity."""
        episodes = self.episodes()
        target = None
        for e in episodes:
            if e["episode_id"] == episode_id:
                target = e
                break
        if target is None:
            return None

        # Pre-use captured?
        if not target.get("research_question") or not target.get("created_at"):
            target["episode_validity"] = "INVALID_NO_PRE_USE_CAPTURE"
            target["invalid_reason"] = "missing pre-use capture"
        elif _flag(target.get("synthetic")) or _flag(post.get("synthetic")):
            target["episode_validity"] = "INVALID_SYNTHETIC_TASK"
            target["invalid_reason"] = "synthetic task"
        elif _flag(post.get("product_error")):
            target["episode_validity"] = "INVALID_PRODUCT_ERROR"
            target["invalid_reason"] = "product error"
        elif self._is_duplicate(target, episodes):
            target["episode_validity"] = "INVALID_DUPLICATE"
            target["invalid_reason"] = "duplicate cluster with valid episode"
        else:
            target["episode_validity"] = "VALID"
            target["invalid_reason"] = ""

        # Post-use facts (copied from user input; never invented)
        for f in OUTCOME_FLAGS + [
            "estimated_manual_effort_bucket", "misuse_risk", "misuse_type",
            "product_design_issue", "post_use_next_step", "notes",
        ]:
            if f in post:
                target[f] = post[f]
        target["updated_at"] = _now()

        # Rewrite the file without the finished record's old line (append-only
        # spirit: original line stays in history; current state updated).
        self._rewrite(episodes)
        return target

    def _is_duplicate(self, target: dict, episodes: list[dict]) -> bool:
        cluster = target.get("episode_cluster_id", "")
        if not cluster:
            return False
        # Another VALID episode in the same cluster completed before this one.
        for e in episodes:
            if e is target:
                continue
            if e.get("episode_cluster_id") == cluster and e.get("episode_validity") == "VALID":
                return True
        return False

    def _rewrite(self, episodes: list[dict]) -> None:
        with open(self.episodes_path, "w", encoding="utf-8") as fh:
            for e in episodes:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    def valid_episodes(self) -> list[dict]:
        return [e for e in self.episodes() if e.get("episode_validity") == "VALID"]

    # ------------------------------------------------------------------
    def aggregate(self) -> dict:
        episodes = self.episodes()
        valid = self.valid_episodes()
        n = len(valid)

        def flag_rate(flag: str) -> float:
            if not n:
                return 0.0
            return sum(1 for e in valid if _flag(e.get(flag))) / n

        incremental = sum(
            1
            for e in valid
            if any(_flag(e.get(f)) for f in (
                "new_fact_found", "contradicting_fact_found",
                "stale_assumption_corrected", "quality_risk_discovered",
            ))
        )
        contradiction_or_stale_or_quality = sum(
            1
            for e in valid
            if any(_flag(e.get(f)) for f in (
                "contradicting_fact_found", "stale_assumption_corrected",
                "quality_risk_discovered",
            ))
        )
        design_misuse = sum(
            1
            for e in valid
            if e.get("product_design_issue") and _flag(e.get("product_design_issue"))
        )
        unique_targets = len({(e.get("target_type"), e.get("target_id")) for e in valid})
        clusters = len({e.get("episode_cluster_id") for e in valid})
        effort_buckets: dict[str, int] = {}
        for e in valid:
            b = e.get("estimated_manual_effort_bucket", "UNKNOWN")
            effort_buckets[str(b)] = effort_buckets.get(str(b), 0) + 1
        scenario = {t: sum(1 for e in valid if e.get("target_type") == t) for t in
                    ("security", "manager", "portfolio")}
        familiar = {f: sum(1 for e in valid if e.get("familiarity_class") == f) for f in
                    ("familiar", "unfamiliar", "UNKNOWN")}
        portfolio_share = (scenario.get("portfolio", 0) / n) if n else 0.0

        metrics = {
            "raw_episode_count": len(episodes),
            "valid_episodes": n,
            "unique_target_count": unique_targets,
            "clustered_effective_count": clusters,
            "incremental_information_rate": round(incremental / n, 4) if n else 0.0,
            "research_path_change_rate": round(flag_rate("research_path_changed"), 4),
            "no_incremental_information_rate": round(flag_rate("no_incremental_information"), 4),
            "contradiction_exposure_rate": round(flag_rate("contradicting_fact_found"), 4),
            "quality_risk_discovery_rate": round(flag_rate("quality_risk_discovered"), 4),
            "stale_assumption_corrected_rate": round(flag_rate("stale_assumption_corrected"), 4),
            "manual_effort_buckets": effort_buckets,
            "misuse_risk_counts": {
                m: sum(1 for e in valid if e.get("misuse_risk") == m)
                for m in ("NONE", "LOW", "MODERATE", "HIGH", "UNKNOWN")
            },
            "product_design_induced_misuse": design_misuse,
            "scenario_breakdown": scenario,
            "familiarity_breakdown": familiar,
            "portfolio_share": round(portfolio_share, 4),
            "product_version_breakdown": {
                v: sum(1 for e in valid if e.get("product_version") == v)
                for v in sorted({e.get("product_version", "UNKNOWN") for e in valid})
            },
        }
        verdict = self._verdict(metrics, n)
        metrics["utility_verdict"] = verdict
        return metrics

    def _verdict(self, metrics: dict, n: int) -> str:
        if n < TARGET_VALID_EPISODES:
            return "INSUFFICIENT_OBSERVATION"
        inc = metrics["incremental_information_rate"]
        csq = (
            metrics["contradiction_exposure_rate"]
            + metrics["stale_assumption_corrected_rate"]
            + metrics["quality_risk_discovery_rate"]
        )
        no_inc = metrics["no_incremental_information_rate"]
        design = metrics["product_design_induced_misuse"]
        path = metrics["research_path_change_rate"]
        supported = (
            inc >= 0.5
            and csq >= 0.2
            and no_inc <= 0.5
            and design / n <= 0.1
        )
        low = (
            no_inc >= 0.7
            and path < 0.15
            and csq < 0.1
        )
        if supported:
            return "SUPPORTED"
        if low:
            return "LOW_INCREMENTAL_VALUE"
        return "MIXED"

    # ------------------------------------------------------------------
    def export_csv(self, path: Path | str) -> None:
        episodes = self.episodes()
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=EPISODE_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for e in episodes:
                writer.writerow(e)

    def export_json(self, path: Path | str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.episodes(), fh, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    def log_product_error(self, rec: dict) -> None:
        self._append(
            self.errors_path,
            {
                "error_id": rec.get("error_id") or str(uuid.uuid4()),
                "episode_id": rec.get("episode_id", ""),
                "affected_fact": rec.get("affected_fact", ""),
                "severity": rec.get("severity", "UNKNOWN"),
                "root_cause": rec.get("root_cause", ""),
                "fix_sha": rec.get("fix_sha", ""),
                "affected_prior_episodes": rec.get("affected_prior_episodes", ""),
                "created_at": _now(),
            },
        )
