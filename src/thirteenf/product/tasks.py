"""Product task universe and deterministic dev/holdout split (v0.4)."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pandas as pd

from thirteenf.product.evidence import ProductStore, VERIFIED_RESOLUTION


TASK_SEED = "13f-product-v0.4-task"
DEV_PCT = 70


def _hash_part(key: str) -> str:
    digest = hashlib.sha256(f"{key}:{TASK_SEED}".encode("utf-8")).hexdigest()
    return "development" if int(digest[:8], 16) % 100 < DEV_PCT else "holdout"


def build_task_universe(
    store: ProductStore, max_per_category: int = 40, max_scan: int = 4000
) -> list[dict]:
    """Deterministic product task pool (security + manager categories)."""
    period = store.latest_period() or ""
    tasks: list[dict] = []

    # Security-level stats
    rows = store.conn.execute(
        """
        SELECT s.cusip, pc.change_type, pc.report_period, pc.manager_id
        FROM position_changes pc
        JOIN securities s ON s.security_id = pc.security_id
        WHERE pc.put_call=''
        """
    ).fetchall()
    latest_actions: dict[str, list[tuple[str, int]]] = {}
    total_obs: dict[str, int] = {}
    for cusip, ct, rp, mid in rows:
        total_obs[cusip] = total_obs.get(cusip, 0) + 1
        if rp == period:
            latest_actions.setdefault(cusip, []).append((ct, int(mid)))
    issuer_of = dict(store.conn.execute("SELECT cusip, issuer FROM securities").fetchall())
    cusip_by_issuer: dict[str, list[str]] = {}
    for c, i in issuer_of.items():
        cusip_by_issuer.setdefault(i, []).append(c)

    def _cand(cusip: str, category: str) -> None:
        tasks.append({"kind": "security", "key": cusip, "category": category})

    scanned = 0
    for cusip in sorted(
        total_obs, key=lambda c: hashlib.sha256(f"sec:{c}:{TASK_SEED}".encode()).hexdigest()
    ):
        if scanned >= max_scan:
            break
        scanned += 1
        acts = latest_actions.get(cusip, [])
        res_status = store._res.get(cusip, {}).get("status", "UNKNOWN")
        etype = store._sem.get(cusip, {}).get("economic_type")
        add = sum(1 for ct, _ in acts if ct in ("NEW", "ADD"))
        red = sum(1 for ct, _ in acts if ct in ("REDUCE", "EXIT"))
        holders = len({m for _, m in acts})
        repeated_add, repeated_reduce = store._security_repeated(cusip)
        issuer = issuer_of.get(cusip, "")
        multi_class = len(cusip_by_issuer.get(issuer, [])) > 1
        stale = cusip not in latest_actions and period and cusip in total_obs
        categories = []
        if holders >= 10:
            categories.append("security_high_breadth")
        if 1 <= holders <= 2:
            categories.append("security_low_breadth")
        if add > 0 and red > 0:
            categories.append("security_mixed_activity")
        if repeated_add >= 1 or repeated_reduce >= 1:
            categories.append("security_persistent_activity")
        if stale:
            categories.append("security_stale")
        if etype == "OPERATING_ADR":
            categories.append("security_adr")
        if multi_class:
            categories.append("security_share_class")
        if res_status not in VERIFIED_RESOLUTION:
            categories.append("security_unresolved_or_ambiguous")
        if total_obs[cusip] <= 3:
            categories.append("security_unfamiliar")
        for cat in categories:
            _cand(cusip, cat)

    # Manager categories
    manager_rows = store.conn.execute(
        "SELECT manager_id, cik FROM managers"
    ).fetchall()
    latest_mids = {
        r[0]
        for r in store.conn.execute(
            "SELECT DISTINCT manager_id FROM filings WHERE report_period=? "
            "AND ingest_status='OK'",
            (period,),
        ).fetchall()
    }
    stale_mids = set(store.stale_manager_ids(period))
    amended_mids = {
        r[0]
        for r in store.conn.execute(
            "SELECT DISTINCT manager_id FROM filings WHERE is_amendment=1 "
            "AND ingest_status='OK'"
        ).fetchall()
    }
    for mid, cik in manager_rows:
        mid = int(mid)
        ev = store.manager_evidence(mid)
        if ev is None:
            continue
        cats = []
        if mid in latest_mids:
            cats.append("manager_current")
        if mid in stale_mids:
            cats.append("manager_stale")
        if ev.position_count and ev.position_count >= 200:
            cats.append("manager_diversified")
        if ev.position_count and ev.position_count <= 20:
            cats.append("manager_concentrated")
        if mid in amended_mids:
            cats.append("manager_amended")
        if ev.quality.get("missing_periods", 0) >= 2:
            cats.append("manager_historically_incomplete")
        for cat in cats:
            tasks.append({"kind": "manager", "key": str(mid), "category": cat})

    # deterministic cap per category by hash
    capped: list[dict] = []
    per_cat: dict[str, int] = {}
    for t in sorted(tasks, key=lambda t: (t["category"], t["key"])):
        if per_cat.get(t["category"], 0) >= max_per_category:
            continue
        per_cat[t["category"]] = per_cat.get(t["category"], 0) + 1
        capped.append(t)
    return capped


def split_tasks(tasks: list[dict]) -> list[dict]:
    out = []
    for t in tasks:
        key = f"{t['kind']}:{t['key']}"
        out.append({**t, "task_id": key, "part": _hash_part(key)})
    return out


def write_manifest(tasks: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["task_id", "kind", "key", "category", "part"])
        writer.writeheader()
        for t in sorted(tasks, key=lambda t: (t["task_id"],)):
            writer.writerow({k: t[k] for k in ("task_id", "kind", "key", "category", "part")})


def load_manifest(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")
