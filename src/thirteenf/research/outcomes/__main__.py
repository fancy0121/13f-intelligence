"""Frozen Outcome Validation CLI (v0.2).

python -m thirteenf.research.outcomes <cmd>
  prices   - fetch full price series for VERIFIED symbols (Yahoo, cached)
  run      - compute the frozen O0/O1_2Q/O1_3Q evaluation grid + null + concentration
  v03      - run the frozen v0.3 Operating Equity outcome validation
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import connect
from thirteenf.research.outcomes.execution import (
    attach_returns,
    build_price_map,
    concentration_audit,
    evaluate_grid,
    fetch_yahoo_series,
    run_null,
)
from thirteenf.research.resolution.coverage import build_observation_frames
from thirteenf.research.outcomes.v03 import falsify, run_v03, write_reports


def cmd_prices(args: argparse.Namespace) -> int:
    price_map, symbol_of = build_price_map(
        None, str(args.out / "security_resolution_master.csv"), args.cache, limit=args.limit
    )
    (args.out / "outcome_price_manifest.json").write_text(
        json.dumps(
            {
                "symbols": len(price_map),
                "errors": {s: p["error"] for s, p in price_map.items() if p.get("error")},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("price symbols:", len(price_map), "errors:", sum(1 for p in price_map.values() if p.get("error")))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    frames = build_observation_frames(conn)
    conn.close()
    symbol_of = None
    price_map = {}
    # Load price series from cache (must run `prices` first).
    master = __import__("pandas").read_csv(args.out / "security_resolution_master.csv", dtype=str).fillna("")
    symbol_of = {
        r["cusip"]: r["symbol"]
        for r in master.to_dict("records")
        if r["status"].startswith("VERIFIED") and r["symbol"]
    }
    symbols = sorted({s for s in symbol_of.values() if s})
    for sym in symbols:
        p = (args.cache / "yahoo_full" / f"{sym.replace('^', '_')}.json")
        if p.exists():
            price_map[sym] = json.loads(p.read_text(encoding="utf-8"))
    bench = price_map.get("^GSPC")
    if bench is None:
        bench = fetch_yahoo_series("^GSPC", args.cache)
        price_map["^GSPC"] = bench
    datasets = attach_returns(frames, symbol_of, price_map, bench)
    grid = evaluate_grid(datasets)
    nulls = {v: {h: run_null(datasets, v, h) for h in ("3M", "6M", "12M")} for v in ("O0", "O1_2Q", "O1_3Q")}
    conc = {
        v: {h: concentration_audit(datasets, v, h) for h in ("3M", "6M", "12M")}
        for v in ("O0", "O1_2Q", "O1_3Q")
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "outcome_execution_results.json").write_text(
        json.dumps(
            {
                "grid": grid,
                "null": nulls,
                "concentration": conc,
                "horizons_days": {"3M": 63, "6M": 126, "12M": 252},
                "generated_utc": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(grid, ensure_ascii=False)[:4000])
    return 0


def cmd_v03(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    results = run_v03(
        conn,
        class_path=str(args.out / "security_semantic_classification.csv"),
        master_path=str(args.out / "security_resolution_master.csv"),
        avail_path=str(args.out / "symbol_history_availability.csv"),
        cache_dir=args.cache,
        out_dir=args.out,
    )
    conn.close()
    verdict = falsify(
        results["outcome_grid"], results["null"], results["concentration"], results["missingness"]
    )
    results["verdict"] = verdict
    (args.out / "v0_3_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    write_reports(results, args.out, verdict)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    print("v0.3 artifacts written")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thirteenf.research.outcomes")
    parser.add_argument("--db", default=str(ROOT / "data" / "thirteenf.db"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "research"))
    parser.add_argument("--cache", default=str(ROOT / "data" / "resolution_cache"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prices")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_prices)
    p2 = sub.add_parser("run")
    p2.set_defaults(func=cmd_run)
    p3 = sub.add_parser("v03")
    p3.set_defaults(func=cmd_v03)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.out = Path(args.out)
    args.cache = Path(args.cache)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
