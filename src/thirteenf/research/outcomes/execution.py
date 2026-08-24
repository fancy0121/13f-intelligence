"""Frozen Outcome Validation execution (v0.2).

Executes O0 / O1_2Q / O1_3Q x {dev, time, manager, security, combined} x
{3M, 6M, 12M} with absolute + benchmark-excess returns, hit rate, median,
downside, dispersion, null comparison, concentration audits. No parameter
tuning; pre-registered horizons only.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from thirteenf.research.outcomes.null_model import NULL_SEED, permute_signals, seeded_rng
from thirteenf.research.outcomes.returns import forward_return
from thirteenf.research.resolution.coverage import build_observation_frames
from thirteenf.research.resolution.sources import price_cache_key, price_symbol

# Pre-registered execution parameters (frozen before running).
HORIZONS_DAYS = {"3M": 63, "6M": 126, "12M": 252}
NULL_REPS = 200


def fetch_yahoo_series(
    symbol: str,
    cache_dir: Path | str,
    *,
    sleep_s: float = 0.35,
    period1: int = 1640995200,  # 2022-01-01
    period2: int = 1780000000,  # 2026-05-28
) -> dict:
    """Full daily series (adjclose) for a symbol, cached on disk."""
    cache_dir = Path(cache_dir)
    yahoo_sym = price_symbol(symbol)
    cache_file = cache_dir / "yahoo_full" / f"{price_cache_key(symbol)}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.request.quote(yahoo_sym)}?period1={period1}&period2={period2}"
        "&interval=1d&events=div%2Csplit"
    )
    result = {"symbol": symbol, "yahoo_symbol": yahoo_sym, "dates": [], "adjclose": [], "splits": {}, "error": None}
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        res = (body.get("chart", {}).get("result") or [None])[0]
        if res is None:
            result["error"] = "no_result"
        else:
            import datetime

            ts = res.get("timestamp") or []
            adj = (res.get("indicators", {}).get("adjclose", [{}])[0] or {}).get("adjclose", [])
            result["dates"] = [
                datetime.datetime.fromtimestamp(t, tz=datetime.timezone.utc).date().isoformat()
                for t in ts
            ]
            result["adjclose"] = [float(a) if a is not None else None for a in adj]
            splits = res.get("events", {}).get("splits", {})
            result["splits"] = {
                datetime.datetime.fromtimestamp(int(k), tz=datetime.timezone.utc).date().isoformat(): v.get("splitRatio")
                for k, v in splits.items()
            }
    except urllib.error.HTTPError as exc:
        result["error"] = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)[:200]
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps({**result, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}),
        encoding="utf-8",
    )
    time.sleep(sleep_s)
    return result


def attach_returns(
    frames: dict[str, pd.DataFrame],
    symbol_of: dict[str, str],
    price_map: dict[str, dict],
    benchmark: dict,
) -> dict[str, pd.DataFrame]:
    """Add 3M/6M/12M absolute and excess returns to each observation."""
    out = {}
    bench_dates = benchmark.get("dates", [])
    bench_adj = benchmark.get("adjclose", [])
    for variant, df in frames.items():
        work = df.copy()
        for horizon, days in HORIZONS_DAYS.items():
            abs_col = f"ret_{horizon}"
            exc_col = f"excess_{horizon}"
            work[abs_col] = None
            work[exc_col] = None
            work[f"censored_{horizon}"] = False
        rows = work.to_dict("records")
        for r in rows:
            sym = symbol_of.get(r["cusip"])
            series = price_map.get(sym) if sym else None
            if not series or series.get("error") or not series.get("dates"):
                continue
            dates = series["dates"]
            adj = series["adjclose"]
            info = r["info_date"]
            for horizon, days in HORIZONS_DAYS.items():
                ret = forward_return(dates, adj, info, days)
                if ret is None:
                    # distinguish censored (series too short) from missing price
                    start = None
                    for i, d in enumerate(dates):
                        if d >= info:
                            start = i
                            break
                    if start is None or start + days >= len(dates):
                        r[f"censored_{horizon}"] = True
                    continue
                r[f"ret_{horizon}"] = ret
                if bench_dates and bench_adj:
                    bret = forward_return(bench_dates, bench_adj, info, days)
                    if bret is not None:
                        r[f"excess_{horizon}"] = ret - bret
        work = pd.DataFrame(rows)
        out[variant] = work
    return out


def evaluate_grid(datasets: dict[str, pd.DataFrame]) -> dict:
    """Metrics grid per variant x split x horizon."""
    results: dict[str, dict] = {}
    parts = ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined")
    for variant, df in datasets.items():
        variant_res: dict = {}
        for part in ("ALL",) + parts:
            sub = df if part == "ALL" else df[df["part"] == part]
            if len(sub) == 0:
                variant_res[part] = {"n": 0, "note": "INSUFFICIENT_SAMPLE"}
                continue
            cell = {"n": int(len(sub))}
            for horizon in HORIZONS_DAYS:
                col = f"excess_{horizon}"
                vals = sub[col].dropna()
                censored = int(sub[f"censored_{horizon}"].sum())
                if len(vals) == 0:
                    cell[horizon] = {"n_ret": 0, "note": "NO_RETURNS"}
                    continue
                neg = vals[vals < 0]
                cell[horizon] = {
                    "n_ret": int(len(vals)),
                    "mean": round(float(vals.mean()), 6),
                    "median": round(float(vals.median()), 6),
                    "hit_rate": round(float((vals > 0).mean()), 6),
                    "std": round(float(vals.std(ddof=0)), 6),
                    "negative_rate": round(float(len(neg) / len(vals)), 6),
                    "mean_negative": round(float(neg.mean()), 6) if len(neg) else None,
                    "right_censored": censored,
                }
            variant_res[part] = cell
        results[variant] = variant_res
    return results


def run_null(datasets: dict[str, pd.DataFrame], variant: str, horizon: str) -> dict:
    """Permutation null on the development cell (frozen seed/reps/rule)."""
    df = datasets[variant]
    dev = df[df["part"] == "H0_dev"].copy()
    col = f"excess_{horizon}"
    dev = dev.dropna(subset=[col])
    if len(dev) == 0:
        return {"variant": variant, "horizon": horizon, "note": "NO_RETURNS"}
    groups = (dev["security_id"].astype(str) + "|" + dev["report_period"]).tolist()
    observed = float(dev[col].median())
    values = dev[col].tolist()
    null_medians = []
    rng = seeded_rng()
    for _ in range(NULL_REPS):
        perm = permute_signals(values, groups, rng)
        null_medians.append(sorted(perm)[len(perm) // 2])
    null_medians.sort()
    p95 = null_medians[int(len(null_medians) * 0.95) - 1]
    return {
        "variant": variant,
        "horizon": horizon,
        "observed_median": observed,
        "null_p95": p95,
        "exceeds_null_p95": observed > p95,
        "null_reps": NULL_REPS,
        "seed": NULL_SEED,
        "n_obs": len(dev),
    }


def concentration_audit(datasets: dict[str, pd.DataFrame], variant: str, horizon: str) -> dict:
    """Leave-one-manager-out + top-security + time-regime on dev."""
    df = datasets[variant]
    dev = df[df["part"] == "H0_dev"].dropna(subset=[f"excess_{horizon}"])
    col = f"excess_{horizon}"
    if len(dev) == 0:
        return {"variant": variant, "horizon": horizon, "note": "NO_RETURNS"}
    base = float(dev[col].median())
    lomo = {}
    for mid in dev["manager_id"].unique():
        sub = dev[dev["manager_id"] != mid]
        lomo[int(mid)] = round(float(sub[col].median()), 6) if len(sub) else None
    # top securities by observation count
    top = dev.groupby("security_id")[col].agg(["count", "median"]).sort_values("count", ascending=False).head(10)
    time_regime = dev.groupby("report_period")[col].median().to_dict()
    return {
        "variant": variant,
        "horizon": horizon,
        "base_median": base,
        "leave_one_manager_out": lomo,
        "top_securities": [
            {"security_id": int(i), "count": int(r["count"]), "median": round(float(r["median"]), 6)}
            for i, r in top.iterrows()
        ],
        "time_regime_median": {k: round(float(v), 6) for k, v in time_regime.items()},
    }


def load_master_map(master_path: str) -> dict[str, str]:
    m = pd.read_csv(master_path, dtype=str).fillna("")
    return {
        r["cusip"]: r["symbol"]
        for r in m.to_dict("records")
        if r["status"].startswith("VERIFIED") and r["symbol"]
    }


def build_price_map(
    conn,
    master_path: str,
    cache_dir: Path,
    *,
    limit: int = 0,
) -> tuple[dict[str, dict], dict[str, str]]:
    symbol_of = load_master_map(master_path)
    price_map: dict[str, dict] = {}
    symbols = sorted({s for s in symbol_of.values() if s})
    if limit:
        symbols = symbols[:limit]
    for i, sym in enumerate(symbols):
        price_map[sym] = fetch_yahoo_series(sym, cache_dir)
        if (i + 1) % 50 == 0:
            print(f"prices {i + 1}/{len(symbols)}", flush=True)
    return price_map, symbol_of
