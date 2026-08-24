"""Security Resolution CLI.

python -m thirteenf.research.resolution <cmd>

Commands:
  pilot      - run the frozen blind pilot (Part A fixed + Part B hash sample)
  scaleup    - resolve the full R0/R1/R2 universe
  pricecheck - check historical availability (Yahoo chart meta) for VERIFIED symbols
  availability - derive availability CSV from cached full price series
  coverage   - compute frozen coverage/bias gates from master + availability

Reads FACT layer only; writes artifacts under reports/research/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from thirteenf.database import connect
from thirteenf.research.resolution.coverage import (
    build_observation_frames,
    build_universe,
    compute_coverage,
    gate_evaluation,
    load_availability,
    load_master,
)
from thirteenf.research.resolution.engine import resolve_cusip
from thirteenf.research.resolution.history import load_historical_symbols
from thirteenf.research.resolution.models import ResolutionStatus
from thirteenf.research.resolution.sources import (
    OpenFIGIClient,
    SECIndex,
    price_cache_key,
)

PART_A = ["02079K305", "874039100", "852234103", "722304102", "G3643J108"]
DEFAULT_BLIND_SEED = "13f-resolution-v0.2.1-pilot-blind"


def _db_securities(conn):
    """CUSIP -> (issuer, title_of_class) from the FACT layer (read-only)."""
    rows = conn.execute(
        """
        SELECT s.cusip, s.issuer,
               (SELECT h.title_of_class FROM holdings h
                WHERE h.cusip = s.cusip AND h.title_of_class != ''
                GROUP BY h.title_of_class
                ORDER BY COUNT(*) DESC, h.title_of_class ASC
                LIMIT 1) AS title_of_class
        FROM securities s
        """
    ).fetchall()
    return {r[0]: {"issuer": r[1], "title_of_class": r[2]} for r in rows}


def _resolve_list(
    cusips: list[str],
    sec_info: dict,
    sec_index: SECIndex,
    historical: dict,
    cache_dir: Path,
    client: OpenFIGIClient | None = None,
) -> list[dict]:
    client = client or OpenFIGIClient(cache_dir / "openfigi")
    jobs = [{"idType": "ID_CUSIP", "idValue": c} for c in cusips]
    responses = client.mapping(jobs)
    rows = []
    for cusip, resp in zip(cusips, responses):
        info = sec_info.get(cusip, {})
        res = resolve_cusip(
            cusip=cusip,
            issuer=info.get("issuer"),
            title_of_class=info.get("title_of_class"),
            of_response=resp,
            sec_index=sec_index,
            historical_map=historical,
        )
        primary = res.records[0] if res.records else None
        rows.append(
            {
                "cusip": cusip,
                "issuer": info.get("issuer", ""),
                "title_of_class": info.get("title_of_class", ""),
                "status": res.status,
                "symbol": primary.symbol if primary else "",
                "exchange": primary.exchange if primary else "",
                "security_type": primary.security_type if primary else "",
                "share_class_figi": primary.share_class_figi if primary else "",
                "figi": primary.figi if primary else "",
                "sources": ";".join(res.sources),
                "notes": " | ".join(res.notes),
            }
        )
    return rows


def cmd_pilot(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    universe = build_universe(conn)
    sec_info = _db_securities(conn)
    conn.close()

    sec_index = SECIndex.build(
        args.cache / "company_tickers.json",
        args.cache / "company_tickers_exchange.json",
    )
    historical = load_historical_symbols(args.historical)
    client = OpenFIGIClient(args.cache / "openfigi")

    # Part A: fixed regression cases.
    part_a = [c for c in PART_A if c in sec_info]
    # Part B: deterministic blind sample.
    eligible = sorted(set(universe["cusip"].tolist()))
    hashed = sorted(
        eligible, key=lambda c: hashlib.sha256(f"{c}:{args.seed}".encode()).hexdigest()
    )[: args.n_blind]
    blind = [c for c in hashed if c not in PART_A]
    sample = part_a + blind

    rows = _resolve_list(sample, sec_info, sec_index, historical, args.cache, client)
    df = pd.DataFrame(rows)
    df.insert(0, "part", ["PART_A" if c in PART_A else "PART_B" for c in df["cusip"]])
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "security_resolution_pilot.csv", index=False)
    summary = {
        "protocol": "v0.2.1",
        "seed": args.seed,
        "n_blind": args.n_blind,
        "part_a": part_a,
        "part_b": blind,
        "status_counts": df["status"].value_counts().to_dict(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.out / "security_resolution_pilot.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("PILOT status counts:", summary["status_counts"])
    print(df[["part", "cusip", "issuer", "status", "symbol", "sources"]].to_string(index=False))
    return 0


def cmd_scaleup(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    universe = build_universe(conn)
    sec_info = _db_securities(conn)
    conn.close()

    sec_index = SECIndex.build(
        args.cache / "company_tickers.json",
        args.cache / "company_tickers_exchange.json",
    )
    historical = load_historical_symbols(args.historical)
    client = OpenFIGIClient(args.cache / "openfigi")

    cusips = sorted(universe["cusip"].tolist())
    if args.limit:
        cusips = cusips[: args.limit]
    # Deterministic order: observation count desc, then cusip.
    order = universe.set_index("cusip")["total_obs"].to_dict()
    cusips = sorted(cusips, key=lambda c: (-order.get(c, 0), c))

    all_rows: list[dict] = []
    for i in range(0, len(cusips), args.batch):
        chunk = cusips[i : i + args.batch]
        rows = _resolve_list(chunk, sec_info, sec_index, historical, args.cache, client)
        all_rows.extend(rows)
        print(f"scaleup {i + len(chunk)}/{len(cusips)}", flush=True)

    df = pd.DataFrame(all_rows)
    uni = universe.set_index("cusip")
    df["r0"] = df["cusip"].map(lambda c: bool(uni.loc[c, "O0"] > 0) if c in uni.index else False)
    df["r1"] = df["cusip"].map(lambda c: bool(uni.loc[c, "O1_2Q"] > 0) if c in uni.index else False)
    df["r2"] = df["cusip"].map(lambda c: bool(uni.loc[c, "O1_3Q"] > 0) if c in uni.index else False)
    df["obs_count"] = df["cusip"].map(lambda c: int(uni.loc[c, "O0"]) if c in uni.index else 0)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "security_resolution_master.csv", index=False)
    summary = {
        "protocol": "v0.2.1",
        "resolved_count": len(df),
        "status_counts": df["status"].value_counts().to_dict(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.out / "security_resolution_scaleup.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary["status_counts"], ensure_ascii=False))
    return 0


def _yahoo_meta(symbol: str, cache_dir: Path, sleep_s: float = 0.5) -> dict:
    import urllib.error
    import urllib.request

    cache_file = cache_dir / "yahoo" / f"{symbol.replace('^', '_')}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.request.quote(symbol)}?range=1d&interval=1d"
    )
    result = {"symbol": symbol, "http": None, "first_trade_date": None, "error": None}
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
            meta = res.get("meta", {})
            ftd = meta.get("firstTradeDate")
            result["http"] = 200
            result["first_trade_date"] = (
                datetime.fromtimestamp(ftd, tz=timezone.utc).date().isoformat()
                if ftd
                else ""
            )
            result["meta_symbol"] = meta.get("symbol", "")
    except urllib.error.HTTPError as exc:
        result["http"] = exc.code
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


def cmd_pricecheck(args: argparse.Namespace) -> int:
    master = load_master(args.out / "security_resolution_master.csv")
    verified = master[master["status"].map(
        lambda s: s in {ResolutionStatus.VERIFIED_EXACT.value,
                        ResolutionStatus.VERIFIED_MULTI_SOURCE.value,
                        ResolutionStatus.VERIFIED_HISTORICAL.value}
    )]
    symbols = sorted({s for s in verified["symbol"] if s})
    rows = []
    for i, sym in enumerate(symbols):
        meta = _yahoo_meta(sym, args.cache, sleep_s=args.sleep)
        rows.append(meta)
        if (i + 1) % 100 == 0:
            print(f"pricecheck {i + 1}/{len(symbols)}", flush=True)
    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "symbol_history_availability.csv", index=False)
    print("pricecheck symbols:", len(symbols))
    return 0


def cmd_availability(args: argparse.Namespace) -> int:
    """Derive symbol_history_availability.csv from cached yahoo_full series."""
    import glob

    master = load_master(args.out / "security_resolution_master.csv")
    verified = master[master["status"].map(
        lambda s: s in {ResolutionStatus.VERIFIED_EXACT.value,
                        ResolutionStatus.VERIFIED_MULTI_SOURCE.value,
                        ResolutionStatus.VERIFIED_HISTORICAL.value}
    )]
    symbols = sorted({s for s in verified["symbol"] if s})
    rows = []
    for sym in symbols:
        cache_file = args.cache / "yahoo_full" / f"{price_cache_key(sym)}.json"
        if not cache_file.exists():
            rows.append({"symbol": sym, "first_trade_date": "", "last_date": "", "http": None, "error": "NOT_FETCHED"})
            continue
        d = json.loads(cache_file.read_text(encoding="utf-8"))
        if d.get("error"):
            rows.append({"symbol": sym, "first_trade_date": "", "last_date": "", "http": None, "error": d["error"]})
            continue
        dates = d.get("dates") or []
        rows.append({
            "symbol": sym,
            "first_trade_date": dates[0] if dates else "",
            "last_date": dates[-1] if dates else "",
            "http": 200,
            "error": "",
        })
    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "symbol_history_availability.csv", index=False)
    print("availability rows:", len(rows))
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    frames = build_observation_frames(conn)
    universe = build_universe(conn)
    conn.close()
    master = load_master(args.out / "security_resolution_master.csv")
    avail_path = args.out / "symbol_history_availability.csv"
    availability = load_availability(avail_path) if avail_path.exists() else None
    coverage = compute_coverage(frames, master, availability)
    gates = gate_evaluation(coverage)
    verified_statuses = {
        ResolutionStatus.VERIFIED_EXACT.value,
        ResolutionStatus.VERIFIED_MULTI_SOURCE.value,
        ResolutionStatus.VERIFIED_HISTORICAL.value,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "security_resolution_coverage.json").write_text(
        json.dumps({"coverage": coverage, "gates": gates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Security Resolution Coverage & Bias Audit (v0.2.1)",
        "",
        f"> Generated: {datetime.now(timezone.utc).isoformat()}",
        f"> Eligible universe securities: {len(universe)}",
        "",
        "## Observation coverage by variant x split",
        "",
        "| Variant | Split | Eligible | Resolved | Coverage % |",
        "|---|---|---|---|---|",
    ]
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        c = coverage[variant]
        lines.append(
            f"| {variant} | ALL | {c['eligible_observations']} | {c['resolved_observations']} | {c['observation_coverage']} |"
        )
        for part in ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined"):
            p = c[part]
            lines.append(
                f"| {variant} | {part} | {p['eligible']} | {p['resolved']} | {p.get('coverage') or p.get('note', '')} |"
            )
    lines.append("")
    lines.append("## Gate evaluation (frozen thresholds)")
    lines.append("")
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        g = gates[variant]
        lines.append(f"- {variant}: overall={g['overall_coverage']}% "
                     f"overall_gate={g['overall_gate']} per_split={g['per_split_gate']} "
                     f"differential={g['differential_gate']} directional={g['directional_gate']} "
                     f"**PASS={g['PASS']}**")
    vb = gates["variant_differential_bias"]
    lines.append(f"- variant differential: O0={vb['O0']}% O1={vb['O1_2Q']}% O2={vb['O1_3Q']}% "
                 f"VARIANT_MAPPING_BIAS={vb['VARIANT_MAPPING_BIAS']}")
    lines.append(f"- security-level coverage: {coverage['security_level']['coverage']}% "
                 f"({coverage['security_level']['resolved_securities']}/{coverage['security_level']['eligible_securities']})")
    lines.append("")
    (args.out / "security_resolution_coverage.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    # ---- Bias audit ----
    obs0 = frames["O0"]
    obs_count = obs0.groupby("cusip").size()
    min_info = obs0.groupby("cusip")["info_date"].min()
    m = master.set_index("cusip")
    m["obs_count"] = obs_count.reindex(m.index).fillna(0).astype(int)
    m["earliest_info_date"] = min_info.reindex(m.index).fillna("")
    avail_map = {}
    if availability is not None and len(availability):
        avail_map = dict(zip(availability["symbol"], availability["first_trade_date"]))
    m["first_trade_date"] = m["symbol"].map(lambda s: avail_map.get(s, ""))
    m["hist_ok"] = m.apply(
        lambda r: bool(r["first_trade_date"]) and bool(r["earliest_info_date"])
        and str(r["first_trade_date"]) <= str(r["earliest_info_date"]),
        axis=1,
    )
    bias_lines = [
        "# Security Resolution Bias Audit (v0.2.1)",
        "",
        f"> Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Mapped vs unmapped",
        "",
    ]
    ver = m[m["status"].isin(verified_statuses)]
    unres = m[~m["status"].isin(verified_statuses)]
    bias_lines.append(f"- securities VERIFIED: {len(ver)} / {len(m)} "
                      f"({round(len(ver)/len(m)*100, 2)}%); UNRESOLVED/other: {len(unres)}")
    bias_lines.append("")
    bias_lines.append("## High- vs low-frequency securities (VERIFIED rate)")
    bias_lines.append("")
    med = float(m["obs_count"].median()) if len(m) else 0
    high = m[m["obs_count"] >= med]
    low = m[m["obs_count"] < med]
    for name, sub in (("high-frequency", high), ("low-frequency", low)):
        rate = sub["status"].isin(verified_statuses).mean() if len(sub) else None
        bias_lines.append(f"- {name}: n={len(sub)} verified_rate={round(rate*100,2) if rate is not None else 'NA'}%")
    bias_lines.append("")
    bias_lines.append("## Common vs ADR (from OpenFIGI securityType)")
    bias_lines.append("")
    for st in ("Common Stock", "ADR", "ETP"):
        sub = m[m["security_type"] == st]
        rate = sub["status"].isin(verified_statuses).mean() if len(sub) else None
        bias_lines.append(f"- {st}: n={len(sub)} verified_rate={round(rate*100,2) if rate is not None else 'NA'}%")
    bias_lines.append("")
    bias_lines.append("## Split / variant coverage")
    bias_lines.append("")
    for variant in ("O0", "O1_2Q", "O1_3Q"):
        c = coverage[variant]
        bias_lines.append(f"- {variant}: overall={c['observation_coverage']}% "
                          f"pos={c['positive_activity']['coverage']}% "
                          f"neg={c['negative_activity']['coverage']}%")
    bias_lines.append("")
    (args.out / "security_resolution_bias_audit.md").write_text(
        "\n".join(bias_lines), encoding="utf-8"
    )

    # ---- Manual resolution queue ----
    queue_statuses = {
        ResolutionStatus.AMBIGUOUS.value,
        ResolutionStatus.CONFLICT.value,
        ResolutionStatus.HISTORICAL_IDENTITY_UNRESOLVED.value,
    }
    part_names_q = ("H0_dev", "H1_time_holdout", "H2_manager_holdout", "H3_security_holdout", "H4_combined")
    variant_cusips = {v: set(frames[v]["cusip"]) for v in ("O0", "O1_2Q", "O1_3Q")}
    part_cusips = {
        v: {p: set(frames[v].loc[frames[v]["part"] == p, "cusip"]) for p in part_names_q}
        for v in ("O0", "O1_2Q", "O1_3Q")
    }
    q = m[m["status"].isin(queue_statuses)].copy()
    q = q.sort_values("obs_count", ascending=False)
    q_rows = []
    for cusip, r in q.iterrows():
        q_rows.append(
            {
                "security_id": "",
                "cusip": cusip,
                "issuer": r.get("issuer", ""),
                "reason": r.get("status", ""),
                "conflicting_evidence": r.get("notes", ""),
                "impacted_observation_count": int(r.get("obs_count", 0)),
                "affected_variants": ";".join(
                    v for v in ("O0", "O1_2Q", "O1_3Q")
                    if cusip in variant_cusips[v]
                ),
                "affected_splits": ";".join(
                    sorted(
                        p
                        for v in ("O0", "O1_2Q", "O1_3Q")
                        for p in part_names_q
                        if cusip in part_cusips[v][p]
                    )
                ),
                "recommended_review_action": (
                    "review conflict evidence"
                    if r.get("status") == ResolutionStatus.CONFLICT.value
                    else "resolve ambiguity"
                    if r.get("status") == ResolutionStatus.AMBIGUOUS.value
                    else "verify historical symbol/price availability"
                ),
            }
        )
    qdf = pd.DataFrame(q_rows)
    qdf.to_csv(args.out / "manual_resolution_queue.csv", index=False)

    # ---- Historical symbol audit ----
    hist_lines = [
        "# Historical Symbol Audit (v0.2.1)",
        "",
        f"> Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Coverage of the observation window by current symbol",
        "",
        "Verified securities whose current-symbol price history does NOT reach the",
        "earliest observation info date are HISTORICAL_IDENTITY_UNRESOLVED (excluded).",
        "",
    ]
    hist_issues = m[(m["status"].isin(verified_statuses)) & (~m["hist_ok"])]
    hist_lines.append(f"- verified with full history: {int(m[m['status'].isin(verified_statuses)]['hist_ok'].sum())}")
    hist_lines.append(f"- verified but history does not reach earliest info date: {len(hist_issues)}")
    if len(hist_issues):
        hist_lines.append("")
        hist_lines.append("| cusip | symbol | earliest_info | first_trade | obs |")
        hist_lines.append("|---|---|---|---|---|")
        for cusip, r in hist_issues.head(40).iterrows():
            hist_lines.append(f"| {cusip} | {r['symbol']} | {r['earliest_info_date']} | {r['first_trade_date']} | {r['obs_count']} |")
    hist_lines.append("")
    hist_lines.append("## Rename / continuity cases (provider-continuity evidence)")
    hist_lines.append("")
    for sym in ("XYZ", "META", "GOOGL", "GOOG", "TSM", "PDD"):
        s = availability[availability["symbol"] == sym] if availability is not None and len(availability) else None
        if s is not None and len(s):
            hist_lines.append(f"- {sym}: first_trade={s.iloc[0]['first_trade_date']} last={s.iloc[0]['last_date']} error={s.iloc[0]['error'] or 'OK'}")
    (args.out / "historical_symbol_audit.md").write_text(
        "\n".join(hist_lines), encoding="utf-8"
    )

    print(json.dumps(gates, ensure_ascii=False, indent=2))
    print("manual queue rows:", len(q_rows))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thirteenf.research.resolution")
    parser.add_argument("--db", default=str(ROOT / "data" / "thirteenf.db"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "research"))
    parser.add_argument("--cache", default=str(ROOT / "data" / "resolution_cache"))
    parser.add_argument("--historical", default=str(ROOT / "config" / "historical_symbols.csv"))
    sub = parser.add_subparsers(dest="command", required=True)

    p_pilot = sub.add_parser("pilot", help="Run frozen blind pilot")
    p_pilot.add_argument("--seed", default=DEFAULT_BLIND_SEED)
    p_pilot.add_argument("--n-blind", type=int, default=50)
    p_pilot.set_defaults(func=cmd_pilot)

    p_scale = sub.add_parser("scaleup", help="Resolve full universe")
    p_scale.add_argument("--limit", type=int, default=0)
    p_scale.add_argument("--batch", type=int, default=100)
    p_scale.set_defaults(func=cmd_scaleup)

    p_price = sub.add_parser("pricecheck", help="Yahoo chart meta availability")
    p_price.add_argument("--sleep", type=float, default=0.5)
    p_price.set_defaults(func=cmd_pricecheck)

    p_avail = sub.add_parser("availability", help="Availability CSV from cached full series")
    p_avail.set_defaults(func=cmd_availability)

    p_cov = sub.add_parser("coverage", help="Coverage/bias gates")
    p_cov.set_defaults(func=cmd_coverage)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.out = Path(args.out)
    args.cache = Path(args.cache)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
