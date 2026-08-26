"""v0.5 real-use observation infrastructure tests."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.product.observation import (
    OUTCOME_FLAGS,
    SUBJECTIVE_FIELDS,
    TARGET_VALID_EPISODES,
    ObservationStore,
)


def _pre(target="security", question="Q"):
    return {
        "target_type": target,
        "target_id": "02079K305",
        "target_label": "GOOGL",
        "research_question": question,
        "pre_use_knowledge": "I know X",
        "pre_use_uncertainties": "not sure",
        "planned_next_step": "check fundamentals",
        "episode_cluster_id": "cluster-1",
    }


def _post(**kw):
    base = {
        "new_fact_found": "true",
        "contradicting_fact_found": "false",
        "stale_assumption_corrected": "false",
        "quality_risk_discovered": "false",
        "research_path_changed": "false",
        "research_time_saved": "false",
        "no_incremental_information": "false",
        "estimated_manual_effort_bucket": "5-15",
        "misuse_risk": "NONE",
        "product_design_issue": "false",
        "post_use_next_step": "next",
    }
    base.update(kw)
    return base


def test_start_episode_no_auto_flags(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    assert ep["episode_validity"] == "PENDING"
    assert ep["new_fact_found"] == 0  # never auto-populated
    assert ep["pre_use_knowledge"] == "I know X"
    assert ep["product_version"]


def test_valid_episode(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    done = s.finish_episode(ep["episode_id"], _post())
    assert done["episode_validity"] == "VALID"


def test_invalid_no_pre_use(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode({"target_type": "security", "target_id": "X"})
    done = s.finish_episode(ep["episode_id"], _post())
    assert done["episode_validity"] == "INVALID_NO_PRE_USE_CAPTURE"


def test_invalid_synthetic(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    done = s.finish_episode(ep["episode_id"], _post(synthetic="true"))
    assert done["episode_validity"] == "INVALID_SYNTHETIC_TASK"


def test_invalid_product_error(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    done = s.finish_episode(ep["episode_id"], _post(product_error="true"))
    assert done["episode_validity"] == "INVALID_PRODUCT_ERROR"


def test_invalid_duplicate_cluster(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    e1 = s.start_episode(_pre(question="Q1"))
    s.finish_episode(e1["episode_id"], _post())
    e2 = s.start_episode(_pre(question="Q2"))
    done = s.finish_episode(e2["episode_id"], _post())
    assert done["episode_validity"] == "INVALID_DUPLICATE"


def test_no_incremental_is_legal_and_not_forced(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    done = s.finish_episode(
        ep["episode_id"],
        _post(new_fact_found="false", no_incremental_information="true"),
    )
    assert done["episode_validity"] == "VALID"
    agg = s.aggregate()
    assert agg["incremental_information_rate"] == 0.0
    assert agg["no_incremental_information_rate"] == 1.0


def test_taxonomy_all_outcome_flags_accepted(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    post = {f: "true" for f in OUTCOME_FLAGS}
    post.update(_post())
    done = s.finish_episode(ep["episode_id"], post)
    assert done["episode_validity"] == "VALID"
    for f in OUTCOME_FLAGS:
        assert done[f] in ("true", "false", "1", "0")


def test_aggregation_excludes_invalid_and_counts_only_valid(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    # 1 valid + 2 invalid
    e1 = s.start_episode(_pre(question="V"))
    s.finish_episode(e1["episode_id"], _post())
    e2 = s.start_episode(_pre(question="S"))
    s.finish_episode(e2["episode_id"], _post(synthetic="true"))
    e3 = s.start_episode(_pre(question="P"))
    s.finish_episode(e3["episode_id"], _post(product_error="true"))
    agg = s.aggregate()
    assert agg["valid_episodes"] == 1
    assert agg["raw_episode_count"] == 3
    assert agg["utility_verdict"] == "INSUFFICIENT_OBSERVATION"


def test_threshold_verdicts_deterministic(tmp_path):
    # Build 20 valid episodes with high incremental -> SUPPORTED
    s = ObservationStore(tmp_path / "obs")
    for i in range(TARGET_VALID_EPISODES):
        post = _post()
        if i % 4 == 0:
            post["contradicting_fact_found"] = "true"
        if i % 5 == 0:
            post["stale_assumption_corrected"] = "true"
        if i % 7 == 0:
            post["quality_risk_discovered"] = "true"
        e = s.start_episode({
            **_pre(),
            "target_id": f"C{i:04d}",
            "target_label": f"T{i}",
            "episode_cluster_id": f"c{i}",
            "research_question": f"Q{i}",
        })
        s.finish_episode(e["episode_id"], post)
    agg = s.aggregate()
    assert agg["valid_episodes"] == 20
    assert agg["utility_verdict"] == "SUPPORTED"

    # 20 valid with all no_incremental -> LOW_INCREMENTAL_VALUE
    s2 = ObservationStore(tmp_path / "obs2")
    for i in range(TARGET_VALID_EPISODES):
        e = s2.start_episode({
            **_pre(),
            "target_id": f"C{i:04d}",
            "episode_cluster_id": f"c{i}",
            "research_question": f"Q{i}",
        })
        s2.finish_episode(
            e["episode_id"],
            _post(new_fact_found="false", no_incremental_information="true"),
        )
    agg2 = s2.aggregate()
    assert agg2["valid_episodes"] == 20
    assert agg2["utility_verdict"] == "LOW_INCREMENTAL_VALUE"


def test_misuse_and_version_tracked(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    done = s.finish_episode(
        ep["episode_id"],
        _post(misuse_risk="HIGH", misuse_type="PRODUCT_DESIGN_INDUCED",
              product_design_issue="true", new_fact_found="true"),
    )
    assert done["misuse_risk"] == "HIGH"
    assert done["misuse_type"] == "PRODUCT_DESIGN_INDUCED"
    assert done["product_design_issue"] == "true"
    agg = s.aggregate()
    assert agg["product_design_induced_misuse"] == 1
    assert done["product_version"]  # version tracked


def test_export_csv_json(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode(_pre())
    s.finish_episode(ep["episode_id"], _post())
    s.export_csv(tmp_path / "out.csv")
    s.export_json(tmp_path / "out.json")
    assert (tmp_path / "out.csv").exists()
    assert (tmp_path / "out.json").exists()
    text = (tmp_path / "out.csv").read_text(encoding="utf-8")
    assert "episode_id" in text
    assert "episode_validity" in text


def test_subjective_fields_never_auto_filled(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    ep = s.start_episode({"target_type": "security", "target_id": "X",
                          "research_question": "Q"})
    for f in SUBJECTIVE_FIELDS:
        assert ep.get(f) in ("", "UNKNOWN", 0, "false"), f
    agg = s.aggregate()
    assert agg["incremental_information_rate"] == 0.0


def test_no_predictive_dependency():
    import thirteenf.product.observation as obs
    src = inspect.getsource(obs)
    assert "research.outcomes" not in src
    assert "forward_return" not in src
    assert "null_model" not in src
    assert "falsif" not in src.lower()
    for w in ("predictive", "score", "signal", "bullish", "bearish",
              "conviction", "smart money", "alpha", "consensus"):
        assert w not in src.lower(), w


def test_product_error_log(tmp_path):
    s = ObservationStore(tmp_path / "obs")
    s.log_product_error({"episode_id": "e1", "affected_fact": "shares",
                         "severity": "HIGH", "root_cause": "mapping"})
    errs = s.errors()
    assert len(errs) == 1
    assert errs[0]["severity"] == "HIGH"
