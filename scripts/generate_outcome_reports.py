"""Generate Outcome Validation v0.2 reports (facts only)."""

from __future__ import annotations

import sys
import json
from datetime import date
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "research"

TODAY = date.today().isoformat()


def write_provider_audit() -> None:
    lines = [
        "# Market Data Provider Audit (Outcome v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "## Candidates evaluated",
        "",
        "| Provider | Free/No key | Prices | Adjusted close | Splits/Dividends | Benchmark | CUSIP→symbol | Verdict |",
        "|---|---|---|---|---|---|---|---|",
        "| Yahoo Finance chart API | Yes | PASS | PASS | PASS (4:1 AAPL split fixture) | PASS (^GSPC) | **FAIL** | REJECT for symbol identity |",
        "| Yahoo search (CUSIP→symbol) | Yes | n/a | n/a | n/a | n/a | **FAIL** (foreign listings first) | REJECT |",
        "| OpenFIGI anonymous mapping | Yes | n/a | n/a | n/a | n/a | FAIL (CUSIP/ISIN unsupported) | REJECT |",
        "| Stooq CSV | Yes | BLOCKED (noindex HTML) | n/a | n/a | n/a | n/a | REJECT |",
        "",
        "## Yahoo chart API — verified capabilities",
        "",
        "- Historical daily prices: PASS (AAPL 2021-01 window, 19 bars returned).",
        "- Adjusted close: PASS (`indicators.adjclose` present).",
        "- Split handling: PASS (`events.splits` with 4:1 ratio for AAPL 2020-08-31).",
        "- Dividend handling: `events=div%2Csplit` supported; adjusted close is "
        "total-return-compatible (dividends reinvested).",
        "- Benchmark: PASS (`^GSPC` returns aligned bars).",
        "- Delisted / unknown symbol: PASS (404 → OUTCOME_UNRESOLVED_SECURITY).",
        "",
        "## Symbol identity resolution — FAIL",
        "",
        "- CUSIP 02079K305 (Alphabet CL A / GOOGL) resolved to `1GOOGL.MI` "
        "(Milan) instead of US-listed GOOGL.",
        "- CUSIP 874039100 (TSMC ADR / TSM) resolved to `0LCV.IL` (London).",
        "- CUSIP 852234103 (Block Inc) resolved to `XYZ`; the historical symbol "
        "was SQ (ticker changed 2026) — symbol-history cannot be reliably "
        "reconstructed from search.",
        "- Direct ticker search returns the correct US listing, but CUSIP→symbol "
        "via search is not auditable (no provenance; foreign listings win).",
        "- OpenFIGI anonymous mapping returns `Invalid value for idType` for "
        "CUSIP and ISIN; only TICKER works (cannot invert CUSIP→symbol).",
        "",
        "## Licensing / usage limitations",
        "",
        "- Yahoo Finance chart/search endpoints are unofficial; no documented "
        "license for bulk automated retrieval. Research-only use, local caching, "
        "no redistribution.",
        "- OpenFIGI anonymous tier: rate-limited; no CUSIP support observed.",
        "",
        "## Conclusion",
        "",
        "No provider passes the full acceptance gate (symbol identity required).",
        "",
        "`FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER`",
    ]
    (OUT / "market_data_provider_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_mapping_coverage() -> None:
    lines = [
        "# Outcome Mapping Coverage (Outcome v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "## Pilot (top-20 securities by holder count)",
        "",
        "- Total eligible CUSIPs probed: 20",
        "- Price-resolved (some symbol): 19/20",
        "- US-listed, auditable resolution: **~16/20** (3 failures: GOOGL→1GOOGL.MI, "
        "TSMC→0LCV.IL, Block→XYZ symbol-history)",
        "- Truly unresolved: 1/20 (PDD 722304102)",
        "",
        "## Full-universe projection (unmapped)",
        "",
        "- Curated symbol mapping file: empty (`config/outcome_symbols.csv` not "
        "populated).",
        "- No CUSIP→symbol mapping is inferred; unresolved securities are "
        "`OUTCOME_UNRESOLVED_SECURITY`.",
        "",
        "## Mapping bias statement",
        "",
        "Because no mapping is used in the formal evaluation, no outcome sample "
        "exists; therefore no selection bias can affect conclusions. When a "
        "curated mapping is later provided, this report must be regenerated "
        "with resolution rate by manager / size / variant.",
        "",
        "`OUTCOME_MAPPING_SELECTION_BIAS` status: NOT_APPLICABLE (no resolved "
        "sample).",
    ]
    (OUT / "outcome_mapping_coverage.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_leakage_audit() -> None:
    rows = [
        ("Quarter-end vs filing-date leakage", "N/A (no outcome run)",
         "Protocol mandates info date = filing_date; framework enforces "
         "first_trading_day_after(info_date)."),
        ("Amendment timing", "N/A", "effective_filing_dates prefers 13F-HR/A; "
         "outcome start follows amendment publication."),
        ("Symbol-history leakage", "DESIGNED", "Curated mappings carry "
         "effective_date; unresolved symbols never guessed."),
        ("Corporate-action leakage", "DESIGNED", "Adjusted close + events; "
         "split fixture tested."),
        ("Benchmark lookahead", "N/A", "No benchmark series fetched in "
         "evaluation (no provider approved)."),
        ("Future delisting knowledge", "N/A", "Missing prices → "
         "OUTCOME_UNRESOLVED_SECURITY; no survivorship filtering."),
        ("Outcome-based sample filtering", "N/A", "No outcome sample created."),
        ("Holdout reuse", "PASS", "Manifests reused from v0.1; no rehash."),
    ]
    lines = [
        "# Outcome Leakage Audit (v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "| Item | Status | Detail |",
        "|---|---|---|",
    ]
    for item, status, detail in rows:
        lines.append(f"| {item} | {status} | {detail} |")
    lines.append("")
    lines.append("Conclusion: no severe leakage identified at framework level; "
                 "formal evaluation not executed (no approved provider).")
    (OUT / "outcome_leakage_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_validation_results() -> None:
    lines = [
        "# Outcome Validation Results (v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "## Status",
        "",
        "`FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER`",
        "",
        "No formal outcome evaluation was executed because no market-data "
        "provider passed the symbol-identity acceptance gate (see "
        "`market_data_provider_audit.md`). Per protocol §4/§8, this is the "
        "correct result — no fabricated outcomes are reported.",
        "",
        "## What would be computed when a provider is approved",
        "",
        "- O0 / O1 / O2 × dev/time/manager/security/combined × 3M/6M/12M",
        "- absolute return, benchmark excess, hit rate, median, dispersion, "
        "downside",
        "- randomized null comparison (NULL_SEED fixed)",
        "- concentration audits (manager / security / time regime)",
    ]
    (OUT / "outcome_validation_results.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_null_results() -> None:
    lines = [
        "# Null Model Results (Outcome v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "- Method: permutation of signal labels within security×quarter groups.",
        "- Seed: `NULL_SEED = \"13f-outcome-v0.2-null\"` (fixed).",
        "- Repetitions pre-registered: 200.",
        "- Comparison rule pre-registered: variant excess-return median must "
        "exceed null 95th percentile in holdout, not only dev.",
        "",
        "## Status",
        "",
        "`NULL_MODEL_EXECUTION=NOT_EXECUTED_NO_APPROVED_PROVIDER`",
        "",
        "The null framework and tests are delivered (`null_model.py`); no "
        "outcome data exists to run it against.",
    ]
    (OUT / "null_model_results.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_concentration_audit() -> None:
    lines = [
        "# Outcome Concentration Audit (v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "- Manager dominance: NOT_EVALUATED (no outcome sample).",
        "- Security dominance: NOT_EVALUATED (no outcome sample).",
        "- Time-regime dependence: NOT_EVALUATED (no outcome sample).",
        "",
        "Frameworks for `ECONOMIC_RESULT_MANAGER_DOMINATED` and "
        "`TIME_REGIME_SENSITIVE` are pre-registered in protocol §19.",
    ]
    (OUT / "outcome_concentration_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_holdout_results() -> None:
    lines = [
        "# Outcome Holdout Results (v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "- Original split manifests reused from v0.1 (no rehash).",
        "- Outcome-resolved subset: empty (no approved provider).",
        "- Dropped observations: none (no sample).",
        "",
        "Status: `NOT_EVALUATED_NO_APPROVED_PROVIDER`.",
    ]
    (OUT / "outcome_holdout_results.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_final_recommendation() -> None:
    lines = [
        "# Outcome Final Recommendation (v0.2)",
        "",
        f"> Generated: {TODAY}",
        "",
        "## Answers",
        "",
        "### O0 — A0",
        "Economic outcome status: **NOT_EVALUATED_NO_APPROVED_PROVIDER**.",
        "Verdict: **BASELINE_ONLY** (no outcome evidence; A0 remains the "
        "simplest baseline).",
        "",
        "### O1 — A1_2Q",
        "Relative to O0: NOT_EVALUATED. Coverage cost: N/A. Holdout behavior: "
        "N/A. Null comparison: N/A.",
        "Verdict: **INSUFFICIENT_EVIDENCE** (structural WEAKLY_SUPPORTED from "
        "v0.1 stands; economic outcome unverified).",
        "",
        "### O2 — A1_3Q",
        "Verdict: **INSUFFICIENT_EVIDENCE** (selection-by-persistence concern "
        "cannot be resolved without outcome data).",
        "",
        "## Simplest surviving rule",
        "",
        "`A0_ONLY` (no complex rule has outcome evidence).",
        "",
        "## Product Candidate",
        "",
        "`PRODUCT_CANDIDATE_STATUS=NO_CANDIDATE`",
        "",
        "## Falsification status",
        "",
        "- O1 falsification criteria: pre-registered; not triggered because "
        "evaluation not executed.",
        "- O2 falsification criteria: pre-registered; O2 not selected over O1 "
        "without evidence.",
    ]
    (OUT / "outcome_final_recommendation.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_frozen_ideas() -> None:
    path = ROOT / "docs" / "rejected_or_frozen_ideas.md"
    lines = [
        "# Rejected or Frozen Ideas (governance freeze)",
        "",
        f"> Updated: {TODAY}",
        "",
        "以下想法状态为 `FROZEN_UNLESS_NEW_EVIDENCE`：未经新证据不得重新引入。",
        "",
        "| Idea | Status | Reason |",
        "|---|---|---|",
        "| Precise manager skill score (e.g. 0.873) | FROZEN | No evidence; "
        "A3 NO_INCREMENTAL_VALUE |",
        "| 0–100 normalized consensus headline | FROZEN | False precision; "
        "not supported |",
        "| A2 portfolio-weight-direction aggregate signal | FROZEN | "
        "NO_INCREMENTAL_VALUE vs A0 |",
        "| Strategy clustering / ML manager ranking | FROZEN | Over-engineered; "
        "no evidence |",
        "| LLM-generated signal | FROZEN | Deterministic-first constitution |",
        "| Portfolio-specific methodology tuning | FROZEN | Portfolio "
        "overfitting prohibited |",
        "",
        "这不是永久禁止研究，而是禁止无证据重新引入。",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_final_manifest() -> None:
    lines = [
        "# FINAL_OUTCOME_RESEARCH_MANIFEST (v0.2)",
        "",
        f"- Generated: {TODAY}",
        "- Protocol freeze SHA: `56b3404115aa00ebad739070b61d841890751412`",
        "- Provider: NO_APPROVED_PROVIDER",
        "- FORWARD_RETURN_EVALUATION=NOT_EVALUATED_NO_APPROVED_PROVIDER",
        "- NULL_SEED: `13f-outcome-v0.2-null`",
        "- Adapter modules: research/outcomes (symbols, returns, null_model)",
        "- Tests: tests/research/test_outcomes.py (8 passed)",
        "- Reports: market_data_provider_audit, outcome_mapping_coverage, "
        "outcome_leakage_audit, outcome_validation_results, null_model_results, "
        "outcome_concentration_audit, outcome_holdout_results, "
        "outcome_final_recommendation",
        "- docs/rejected_or_frozen_ideas.md updated",
        "- Status: OUTCOME_VALIDATION_STATUS=PARTIAL_NO_APPROVED_MARKET_DATA",
        "- PRODUCT_METHODOLOGY_STATUS=NO_RULE_APPROVED",
        "- REAL_WORLD_DECISION_UTILITY=PENDING",
    ]
    (OUT / "FINAL_OUTCOME_RESEARCH_MANIFEST.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_machine_readable_manifest() -> None:
    """Machine-readable outcome manifest (JSON) - facts only."""
    # Eligible counts sourced from the committed v0.1 research_manifest.json.
    v01 = json.loads((OUT / "research_manifest.json").read_text(encoding="utf-8"))
    eligible = {}
    for variant in ("A0", "A1_2Q", "A1_3Q"):
        eligible[variant] = {
            "H0_dev": v01["results"][variant]["H0_dev"]["eligible"],
            "H1_time_holdout": v01["results"][variant]["H1_time_holdout"]["eligible"],
            "H2_manager_holdout": v01["results"][variant]["H2_manager_holdout"]["eligible"],
            "H3_security_holdout": v01["results"][variant]["H3_security_holdout"]["eligible"],
            "H4_combined": v01["results"][variant]["H4_combined"]["eligible"],
        }
    manifest = {
        "outcome_protocol_version": "v0.2",
        "outcome_protocol_freeze_sha": "56b3404115aa00ebad739070b61d841890751412",
        "provider": "NO_APPROVED_PROVIDER",
        "forward_return_evaluation": "NOT_EVALUATED_NO_APPROVED_PROVIDER",
        "null_seed": "13f-outcome-v0.2-null",
        "null_repetitions": 200,
        "outcome_status": "PARTIAL_NO_APPROVED_MARKET_DATA",
        "product_methodology_status": "NO_RULE_APPROVED",
        "product_candidate_status": "NO_CANDIDATE",
        "real_world_decision_utility": "PENDING",
        "eligible_observations_by_variant_and_split": eligible,
        "pilot_mapping_summary": {
            "probed_cusips": 20,
            "price_resolved": 19,
            "us_listed_auditable": 16,
            "unresolved": 1,
            "known_symbol_issues": [
                "02079K305->1GOOGL.MI (foreign listing, should be US GOOGL)",
                "874039100->0LCV.IL (foreign listing, should be US TSM)",
                "852234103->XYZ (symbol-history: SQ renamed to XYZ 2026)",
            ],
        },
        "generated": date.today().isoformat(),
    }
    (OUT / "outcome_research_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_pilot_coverage_csv() -> None:
    """Machine-readable pilot mapping coverage (CSV) - facts recorded from the
    2026-08-24 pilot run against Yahoo Finance (research-only)."""
    rows = [
        ("023135106", 23, "AMZN", "NMS", 1255, "RESOLVED_US"),
        ("02079K305", 21, "1GOOGL.MI", "MIL", 1271, "FOREIGN_LISTING_ISSUE"),
        ("30303M102", 20, "META", "NMS", 1255, "RESOLVED_US"),
        ("594918104", 19, "MSFT", "NMS", 1255, "RESOLVED_US"),
        ("67066G104", 18, "NVDA", "NMS", 1255, "RESOLVED_US"),
        ("92826C839", 17, "V", "NYQ", 1255, "RESOLVED_US"),
        ("874039100", 17, "0LCV.IL", "IOB", 1216, "FOREIGN_LISTING_ISSUE"),
        ("11135F101", 17, "AVGO", "NMS", 1255, "RESOLVED_US"),
        ("G3643J108", 16, "FLUT", "NYQ", 1255, "RESOLVED_US"),
        ("91324P102", 16, "UNH", "NYQ", 1255, "RESOLVED_US"),
        ("852234103", 16, "XYZ", "NYQ", 1255, "SYMBOL_HISTORY_ISSUE"),
        ("722304102", 16, "", "", 0, "UNRESOLVED"),
        ("235851102", 16, "DHR", "NYQ", 1255, "RESOLVED_US"),
        ("02079K107", 16, "GOOG", "NMS", 1255, "RESOLVED_US"),
        ("90353T100", 15, "UBER", "NYQ", 1255, "RESOLVED_US"),
        ("833445109", 15, "SNOW", "NYQ", 1255, "RESOLVED_US"),
        ("79466L302", 15, "CRM", "NYQ", 1255, "RESOLVED_US"),
        ("25809K105", 15, "DASH", "NMS", 1255, "RESOLVED_US"),
        ("22266T109", 15, "CPNG", "NYQ", 1209, "RESOLVED_US"),
        ("14040H105", 15, "COF", "NYQ", 1255, "RESOLVED_US"),
    ]
    lines = [
        "# pilot mapping coverage recorded 2026-08-24 (Yahoo research-only; "
        "not an approved provider)",
        "cusip,holders,symbol,exchange,bars,status",
    ]
    for cusip, holders, symbol, exch, bars, status in rows:
        lines.append(f"{cusip},{holders},{symbol},{exch},{bars},{status}")
    (OUT / "outcome_pilot_mapping_coverage.csv").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> int:
    write_provider_audit()
    write_mapping_coverage()
    write_leakage_audit()
    write_validation_results()
    write_null_results()
    write_concentration_audit()
    write_holdout_results()
    write_final_recommendation()
    write_frozen_ideas()
    write_final_manifest()
    write_machine_readable_manifest()
    write_pilot_coverage_csv()
    print("outcome reports generated in", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
