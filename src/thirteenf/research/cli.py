"""Unified research CLI: python -m thirteenf.research run --protocol v0.1"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.database import connect, init_db
from thirteenf.research.experiments import (
    a0_signals,
    a1_signals,
    a2_signals,
    a3_stratified,
    load_observations,
    manager_characteristics,
)
from thirteenf.research.metrics import (
    coverage,
    leave_one_manager_out,
    sign_stability,
)
from thirteenf.research.splits import (
    COMMON_WINDOW_END,
    COMMON_WINDOW_START,
    manager_split,
    protocol_time_split,
    security_split,
    time_split,
    write_manifest,
)


def _sanitize(obj):
    """Recursively convert numpy/pandas scalars and NaN to JSON-safe values."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if hasattr(obj, "item"):  # numpy int/float/bool scalars
        try:
            return _sanitize(obj.item())
        except (ValueError, TypeError):
            pass
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _apply_splits(obs: pd.DataFrame, conn) -> pd.DataFrame:
    m_split = manager_split(conn)
    s_split = security_split(conn)
    obs = obs.copy()
    obs["manager_part"] = obs["manager_id"].map(m_split)
    obs["security_part"] = obs["cusip"].map(s_split)
    return obs


def cmd_run(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    obs = load_observations(conn)
    obs = _apply_splits(obs, conn)

    periods = sorted(obs["report_period"].unique().tolist())
    # Protocol v0.1 frozen window; implementation bug fixed 2026-08-24:
    # previously used time_split() over ALL periods (2021..2026), which put the
    # sparse early quarters in development and the bulk in holdout. Now the
    # 12-quarter common window is enforced, dev = 2023-09-30..2025-06-30,
    # holdout = 2025-09-30..2026-06-30.
    dev_periods, holdout_periods = protocol_time_split(periods)
    obs = obs[
        obs["report_period"].between(COMMON_WINDOW_START, COMMON_WINDOW_END)
    ].copy()

    results: dict[str, dict] = {}
    artifacts: dict[str, pd.DataFrame] = {}

    for variant, fn, score_col in (
        ("A0", lambda o: a0_signals(o), "net_directional"),
        ("A1_2Q", lambda o: a1_signals(o, k=2), "net_directional"),
        ("A1_3Q", lambda o: a1_signals(o, k=3), "net_directional"),
        ("A2", lambda o: a2_signals(o), "net_weight_direction"),
    ):
        full = fn(obs)
        artifacts[f"{variant}_full"] = full
        # Build per-observation variant frames for holdout evaluation by
        # masking observations and recomputing signals (never reuses holdout
        # rows in fit).
        parts = {
            "H0_dev": obs[
                obs["report_period"].isin(dev_periods)
                & (obs["manager_part"] == "development")
                & (obs["security_part"] == "development")
            ],
            "H1_time_holdout": obs[
                obs["report_period"].isin(holdout_periods)
                & (obs["manager_part"] == "development")
                & (obs["security_part"] == "development")
            ],
            "H2_manager_holdout": obs[
                obs["report_period"].isin(dev_periods)
                & (obs["manager_part"] == "holdout")
                & (obs["security_part"] == "development")
            ],
            "H3_security_holdout": obs[
                obs["report_period"].isin(dev_periods)
                & (obs["manager_part"] == "development")
                & (obs["security_part"] == "holdout")
            ],
            "H4_combined": obs[
                obs["report_period"].isin(holdout_periods)
                & (obs["manager_part"] == "holdout")
                & (obs["security_part"] == "holdout")
            ],
        }
        variant_result = {"variant": variant, "score_col": score_col}
        for part_name, part_obs in parts.items():
            if len(part_obs) == 0:
                variant_result[part_name] = {"n": 0, "note": "INSUFFICIENT_SAMPLE"}
                continue
            sig = fn(part_obs)
            cov = coverage(sig)
            stab = sign_stability(sig, score_col)
            variant_result[part_name] = {
                "n_obs": len(part_obs),
                **cov,
                **stab,
            }
        # Dominance audit on H0 only (pre-registered).
        h0_obs = parts["H0_dev"]
        if len(h0_obs) > 0:
            dom = leave_one_manager_out(h0_obs, fn, score_col)
            variant_result["dominance"] = dom
        results[variant] = variant_result

    # Manager characteristics (A3 input) - report only, no production write.
    chars = manager_characteristics(conn)
    artifacts["manager_characteristics"] = chars

    # A3: stratified analysis within manager characteristic buckets (H0 only,
    # as pre-registered for A3; per-bucket results are descriptive).
    a3_results: dict[str, dict] = {}
    for feature in ("filing_continuity", "avg_concentration"):
        stratified = a3_stratified(
            obs[obs["report_period"].isin(dev_periods)],
            chars,
            feature=feature,
        )
        for bucket, sig in stratified.items():
            cov = coverage(sig)
            stab = sign_stability(sig, "net_weight_direction")
            a3_results[f"A3_{feature}_{bucket}"] = {
                "feature": feature,
                "bucket": bucket,
                **cov,
                **stab,
            }
            artifacts[f"A3_{feature}_{bucket}_signals"] = sig
    if a3_results:
        results["A3"] = {"variant": "A3", "score_col": "net_weight_direction",
                         "buckets": a3_results}

    # Write artifacts.
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in artifacts.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)

    # Manifests
    m_split = manager_split(conn)
    s_split = security_split(conn)
    write_manifest(
        out_dir / "time_split_manifest.csv",
        [
            {"period": p, "part": "development" if p in dev_periods else "holdout"}
            for p in periods
        ],
        header="time split manifest",
    )
    write_manifest(
        out_dir / "manager_split_manifest.csv",
        [
            {"manager_id": k, "part": v}
            for k, v in sorted(m_split.items())
        ],
        header="manager split manifest",
    )
    write_manifest(
        out_dir / "security_split_manifest.csv",
        [
            {"cusip": k, "part": v}
            for k, v in sorted(s_split.items())
        ],
        header="security split manifest (sample)",
    )

    manifest = {
        "protocol_version": "v0.1",
        "git_sha": args.git_sha,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "db_snapshot": args.db,
        "quarters_dev": dev_periods,
        "quarters_holdout": holdout_periods,
        "variants": list(results.keys()),
        "results": results,
    }
    (out_dir / "research_manifest.json").write_text(
        json.dumps(_sanitize(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    conn.close()
    print(json.dumps({"variants": list(results)}, ensure_ascii=False))
    for v, r in results.items():
        print(v, json.dumps(_sanitize(r), ensure_ascii=False)[:600])
    print(f"artifacts={out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thirteenf.research")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run pre-registered research protocol")
    run.add_argument("--protocol", default="v0.1")
    run.add_argument("--db", default=str(ROOT / "data" / "thirteenf.db"))
    run.add_argument("--out", default=str(ROOT / "reports" / "research"))
    run.add_argument("--dev-quarters", type=int, default=8)
    run.add_argument("--git-sha", default="unknown")
    run.set_defaults(func=cmd_run)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
