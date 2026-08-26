"""Product evidence queries and derived facts (deterministic, offline)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from thirteenf.database import connect


VERIFIED_RESOLUTION = frozenset(
    {"VERIFIED_EXACT", "VERIFIED_MULTI_SOURCE", "VERIFIED_HISTORICAL"}
)
CHANGE_TYPES = ("NEW", "ADD", "REDUCE", "EXIT", "UNCHANGED")
EXPECTED_STALE_DAYS = 180


def _direction(ct: str) -> int:
    if ct in ("NEW", "ADD"):
        return 1
    if ct in ("REDUCE", "EXIT"):
        return -1
    return 0


def _days_since(d: str) -> int | None:
    if not d:
        return None
    try:
        return (date.today() - date.fromisoformat(d)).days
    except ValueError:
        return None


@dataclass(frozen=True)
class ManagerEvidence:
    manager_id: int
    name: str
    cik: str
    validation_status: str
    latest_report_period: str | None
    latest_filing_date: str | None
    days_since_filing: int | None
    stale: bool
    amended: bool
    position_count: int
    total_value: float | None
    top_holdings: list[dict] = field(default_factory=list)
    latest_changes: dict[str, list[dict]] = field(default_factory=dict)
    repeated: dict[str, int] = field(default_factory=dict)
    quality: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SecurityEvidence:
    key: str
    cusip: str
    issuer: str | None
    ticker: str | None
    resolution_status: str
    economic_type: str | None
    classification_status: str | None
    latest_report_period: str | None
    latest_filing_date: str | None
    days_since_filing: int | None
    holder_entity_count: int
    verified_independent_manager_count: int
    activity_counts: dict[str, int]
    activity_state: str
    independent_add_manager_count: int = 0
    independent_reduce_manager_count: int = 0
    independent_new_manager_count: int = 0
    independent_exit_manager_count: int = 0
    holders: list[dict] = field(default_factory=list)
    repeated_add_manager_count: int = 0
    repeated_reduce_manager_count: int = 0
    timeline: list[dict] = field(default_factory=list)
    quality: dict = field(default_factory=dict)


class ProductStore:
    """Read-only evidence store. No live external calls."""

    def __init__(
        self,
        db_path: Path | str,
        resolution_csv: Path | str,
        semantic_csv: Path | str,
        managers_csv: Path | str,
    ) -> None:
        self.conn: sqlite3.Connection = connect(db_path)
        self.resolution = pd.read_csv(resolution_csv, dtype=str).fillna("")
        self.semantic = pd.read_csv(semantic_csv, dtype=str).fillna("")
        self.managers = pd.read_csv(managers_csv, dtype=str).fillna("")
        self._res = self.resolution.set_index("cusip").to_dict("index")
        self._sem = self.semantic.set_index("cusip").to_dict("index")
        # manager_id -> validation status (by CIK)
        cik_to_id = {
            str(r[0]): r[1]
            for r in self.conn.execute("SELECT cik, manager_id FROM managers").fetchall()
        }
        self._mgr_status: dict[int, str] = {}
        for _, r in self.managers.iterrows():
            cik = str(r.get("cik", "")).strip()
            mid = cik_to_id.get(cik)
            if mid is not None:
                self._mgr_status[int(mid)] = str(r.get("validation_status", "")).strip()
        self._quarters = self._load_quarters()
        self._repeated_cache: dict[str, tuple[int, int]] | None = None

    def close(self) -> None:
        self.conn.close()

    def _load_quarters(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT report_period FROM filings WHERE ingest_status='OK'"
        ).fetchall()
        return sorted(r[0] for r in rows)

    # ------------------------------------------------------------------
    # Managers / overview
    # ------------------------------------------------------------------
    def latest_period(self) -> str | None:
        row = self.conn.execute(
            "SELECT MAX(report_period) FROM filings WHERE ingest_status='OK'"
        ).fetchone()
        return row[0] if row else None

    def manager_update_counts(self, period: str) -> tuple[int, int]:
        total = self.conn.execute("SELECT COUNT(*) FROM managers").fetchone()[0]
        updated = self.conn.execute(
            "SELECT COUNT(DISTINCT manager_id) FROM filings "
            "WHERE report_period=? AND ingest_status='OK'",
            (period,),
        ).fetchone()[0]
        return updated, total

    def manager_latest_filing(self, manager_id: int) -> tuple[str | None, str | None, bool]:
        row = self.conn.execute(
            """
            SELECT report_period, filing_date, MAX(is_amendment)
            FROM filings
            WHERE manager_id=? AND ingest_status='OK'
            GROUP BY report_period
            ORDER BY report_period DESC LIMIT 1
            """,
            (manager_id,),
        ).fetchone()
        if not row:
            return None, None, False
        return row[0], row[1], bool(row[2])

    def stale_manager_ids(self, period: str) -> list[int]:
        """Managers without a filing for the latest period (or very old)."""
        updated = {
            r[0]
            for r in self.conn.execute(
                "SELECT DISTINCT manager_id FROM filings "
                "WHERE report_period=? AND ingest_status='OK'",
                (period,),
            ).fetchall()
        }
        mids = [r[0] for r in self.conn.execute("SELECT manager_id FROM managers").fetchall()]
        stale = []
        for mid in mids:
            if mid not in updated:
                stale.append(mid)
                continue
            _, fdate, _ = self.manager_latest_filing(mid)
            days = _days_since(fdate or "")
            if days is not None and days > EXPECTED_STALE_DAYS:
                stale.append(mid)
        return stale

    def amendment_count(self, period: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM filings WHERE report_period=? AND is_amendment=1 "
            "AND ingest_status='OK'",
            (period,),
        ).fetchone()[0]

    def resolution_summary(self) -> dict[str, int]:
        return self.resolution["status"].value_counts().to_dict()

    def quality_events(self) -> list[tuple[str, str, int]]:
        return self.conn.execute(
            "SELECT event_type, severity, COUNT(*) FROM quality_events "
            "GROUP BY event_type, severity ORDER BY severity, event_type"
        ).fetchall()

    def event_counts(self, period: str) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT change_type, COUNT(*)
            FROM position_changes
            WHERE report_period=? AND put_call=''
            GROUP BY change_type
            """,
            (period,),
        ).fetchall()
        out = {c: 0 for c in CHANGE_TYPES}
        for ct, n in rows:
            out[ct] = int(n)
        return out

    def managers_list(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT manager_id, name, cik FROM managers ORDER BY name"
        ).fetchall()
        return [
            {
                "manager_id": r[0],
                "name": r[1],
                "cik": str(r[2]),
                "validation_status": self._mgr_status.get(int(r[0]), "UNKNOWN"),
            }
            for r in rows
        ]

    def _is_independent(self, manager_id: int) -> bool:
        return self._mgr_status.get(int(manager_id)) in ("VERIFIED", "VERIFIED_WITH_SCOPE")

    # ------------------------------------------------------------------
    # Manager evidence (Scenario A)
    # ------------------------------------------------------------------
    def manager_evidence(self, manager_id: int) -> ManagerEvidence | None:
        mid = int(manager_id)
        row = self.conn.execute(
            "SELECT name, cik FROM managers WHERE manager_id=?", (mid,)
        ).fetchone()
        if not row:
            return None
        period, fdate, amended = self.manager_latest_filing(mid)
        stale = False
        latest = self.latest_period()
        if latest and (period is None or period != latest):
            stale = True
        days = _days_since(fdate or "")
        if days is not None and days > EXPECTED_STALE_DAYS:
            stale = True
        # snapshot
        snap = self.conn.execute(
            """
            SELECT COUNT(*), SUM(value)
            FROM holdings h JOIN filings f ON f.filing_id=h.filing_id
            WHERE f.manager_id=? AND f.report_period=? AND f.ingest_status='OK'
            """,
            (mid, period or ""),
        ).fetchone()
        pos_count = int(snap[0] or 0)
        total_value = float(snap[1]) if snap[1] is not None else None
        top = self.conn.execute(
            """
            SELECT h.cusip, h.issuer, h.shares, h.value, h.portfolio_weight,
                   h.put_call
            FROM holdings h JOIN filings f ON f.filing_id=h.filing_id
            WHERE f.manager_id=? AND f.report_period=? AND f.ingest_status='OK'
            ORDER BY h.value DESC LIMIT 10
            """,
            (mid, period or ""),
        ).fetchall()
        top_holdings = [
            {
                "cusip": t[0],
                "issuer": t[1],
                "shares": t[2],
                "value": t[3],
                "weight": t[4],
                "put_call": t[5],
                "resolution_status": self._res.get(t[0], {}).get("status", "UNKNOWN"),
                "ticker": self._res.get(t[0], {}).get("symbol", ""),
            }
            for t in top
        ]
        # latest changes
        changes = {c: [] for c in CHANGE_TYPES}
        rows = self.conn.execute(
            """
            SELECT s.cusip, pc.change_type, pc.shares_prev, pc.shares_now,
                   pc.weight_prev, pc.weight_now
            FROM position_changes pc
            JOIN securities s ON s.security_id = pc.security_id
            WHERE pc.manager_id=? AND pc.report_period=? AND pc.put_call=''
            ORDER BY pc.change_type, ABS(COALESCE(pc.share_change_pct,0)) DESC
            """,
            (mid, period or ""),
        ).fetchall()
        for r in rows:
            changes[r[1]].append(
                {
                    "cusip": r[0],
                    "issuer": self.conn.execute(
                        "SELECT issuer FROM securities WHERE cusip=?", (r[0],)
                    ).fetchone()[0] if self.conn.execute(
                        "SELECT 1 FROM securities WHERE cusip=?", (r[0],)
                    ).fetchone() else None,
                    "shares_prev": r[2],
                    "shares_now": r[3],
                    "weight_prev": r[4],
                    "weight_now": r[5],
                    "resolution_status": self._res.get(r[0], {}).get("status", "UNKNOWN"),
                }
            )
        # repeated activity
        repeated = self._manager_repeated(mid)
        # quality
        unresolved = sum(
            1
            for h in top_holdings
            if h["resolution_status"] not in VERIFIED_RESOLUTION
        )
        missing_periods = 0
        if latest:
            mgr_periods = {
                r[0]
                for r in self.conn.execute(
                    "SELECT DISTINCT report_period FROM filings "
                    "WHERE manager_id=? AND ingest_status='OK'",
                    (mid,),
                ).fetchall()
            }
            missing_periods = sum(1 for q in self._quarters if q not in mgr_periods)
        return ManagerEvidence(
            manager_id=mid,
            name=row[0],
            cik=str(row[1]),
            validation_status=self._mgr_status.get(mid, "UNKNOWN"),
            latest_report_period=period,
            latest_filing_date=fdate,
            days_since_filing=days,
            stale=stale,
            amended=amended,
            position_count=pos_count,
            total_value=total_value,
            top_holdings=top_holdings,
            latest_changes=changes,
            repeated=repeated,
            quality={
                "unresolved_or_conflict_top10": unresolved,
                "missing_periods": missing_periods,
                "amended": amended,
                "stale": stale,
            },
        )

    def _manager_repeated(self, manager_id: int) -> dict[str, int]:
        """Max consecutive-same-direction run per (manager, security) across
        the manager's own filed periods; no gap crossing."""
        filed = {
            r[0]
            for r in self.conn.execute(
                "SELECT DISTINCT report_period FROM filings "
                "WHERE manager_id=? AND ingest_status='OK'",
                (manager_id,),
            ).fetchall()
        }
        qpos = {q: i for i, q in enumerate(self._quarters)}
        rows = self.conn.execute(
            """
            SELECT security_id, report_period, change_type
            FROM position_changes
            WHERE manager_id=? AND put_call=''
            ORDER BY security_id, report_period
            """,
            (manager_id,),
        ).fetchall()
        add_runs = 0
        reduce_runs = 0
        cur_sec = None
        prev_period = None
        prev_dir = 0
        run = 0
        for sec, period, ct in rows:
            if sec != cur_sec:
                cur_sec = sec
                prev_period = None
                prev_dir = 0
                run = 0
            d = _direction(ct)
            consecutive = (
                prev_period is not None
                and period in filed
                and prev_period in filed
                and qpos.get(period) is not None
                and qpos.get(prev_period) is not None
                and qpos[period] == qpos[prev_period] + 1
            )
            if d != 0 and prev_dir == d and consecutive:
                run += 1
            else:
                run = 1
            if d != 0:
                if d == 1:
                    add_runs = max(add_runs, run)
                else:
                    reduce_runs = max(reduce_runs, run)
            prev_period = period
            prev_dir = d
        return {
            "repeated_add_manager_count": 1 if add_runs >= 2 else 0,
            "repeated_reduce_manager_count": 1 if reduce_runs >= 2 else 0,
        }

    # ------------------------------------------------------------------
    # Security evidence (Scenario B)
    # ------------------------------------------------------------------
    def security_search(self, query: str) -> list[dict]:
        q = (query or "").strip().upper()
        if not q:
            return []
        out = []
        seen = set()
        # by verified ticker
        for cusip, r in self._res.items():
            sym = str(r.get("symbol", "")).upper()
            if sym == q and r.get("status") in VERIFIED_RESOLUTION and cusip not in seen:
                out.append({"cusip": cusip, "match_type": "ticker", "ticker": sym})
                seen.add(cusip)
        # by CUSIP
        if q in self._res and q not in seen:
            out.append({"cusip": q, "match_type": "cusip",
                        "ticker": self._res[q].get("symbol", "")})
            seen.add(q)
        # by issuer (all matches)
        rows = self.conn.execute(
            "SELECT cusip, issuer FROM securities WHERE UPPER(issuer) LIKE ?",
            (f"%{q}%",),
        ).fetchall()
        for cusip, issuer in rows:
            if cusip in seen:
                continue
            if cusip in self._res:
                out.append({"cusip": cusip, "match_type": "issuer", "ticker": self._res[cusip].get("symbol", "")})
                seen.add(cusip)
        return out

    def security_evidence(self, cusip: str) -> SecurityEvidence | None:
        cusip = cusip.upper()
        issuer_row = self.conn.execute(
            "SELECT issuer FROM securities WHERE cusip=?", (cusip,)
        ).fetchone()
        if issuer_row is None:
            return None
        res = self._res.get(cusip, {"status": "UNKNOWN", "symbol": ""})
        sem = self._sem.get(cusip, {})
        # latest period among holders
        latest = self.latest_period() or ""
        rows = self.conn.execute(
            """
            SELECT pc.manager_id, m.name, pc.change_type, pc.shares_prev,
                   pc.shares_now, pc.share_change_pct, pc.weight_prev,
                   pc.weight_now, pc.weight_change, pc.report_period
            FROM position_changes pc
            JOIN securities s ON s.security_id = pc.security_id
            JOIN managers m ON m.manager_id=pc.manager_id
            WHERE s.cusip=? AND pc.put_call='' AND pc.report_period=?
            ORDER BY m.name
            """,
            (cusip, latest),
        ).fetchall()
        holders = [
            {
                "manager_id": r[0],
                "manager": r[1],
                "independent": self._is_independent(r[0]),
                "change_type": r[2],
                "shares_prev": r[3],
                "shares_now": r[4],
                "share_change_pct": r[5],
                "weight_prev": r[6],
                "weight_now": r[7],
                "weight_change": r[8],
                "report_period": r[9],
            }
            for r in rows
        ]
        holder_entity_count = len({h["manager_id"] for h in holders})
        independent_count = sum(1 for h in holders if h["independent"])
        activity = {c: 0 for c in CHANGE_TYPES}
        indep_add = indep_reduce = 0
        indep_new = indep_exit = 0
        for h in holders:
            activity[h["change_type"]] += 1
            if h["independent"]:
                if h["change_type"] in ("NEW", "ADD"):
                    indep_add += 1
                elif h["change_type"] in ("REDUCE", "EXIT"):
                    indep_reduce += 1
                if h["change_type"] == "NEW":
                    indep_new += 1
                if h["change_type"] == "EXIT":
                    indep_exit += 1
        activity_state = self._activity_state(holders, indep_add, indep_reduce)
        # filing freshness (max filing date across holders for latest period)
        fdate = None
        if latest:
            row = self.conn.execute(
                """
                SELECT MAX(f.filing_date) FROM filings f
                WHERE f.report_period=? AND f.ingest_status='OK'
                """,
                (latest,),
            ).fetchone()
            fdate = row[0] if row else None
        # repeated counts across independent managers
        rep_add, rep_reduce = self._security_repeated(cusip)
        # timeline
        timeline = []
        for period in self._quarters:
            n = self.conn.execute(
                """
                SELECT COUNT(*),
                       SUM(CASE WHEN pc.change_type IN ('NEW','ADD') THEN 1 ELSE 0 END),
                       SUM(CASE WHEN pc.change_type IN ('REDUCE','EXIT') THEN 1 ELSE 0 END)
                FROM position_changes pc
                JOIN securities s ON s.security_id = pc.security_id
                WHERE s.cusip=? AND pc.report_period=? AND pc.put_call=''
                """,
                (cusip, period),
            ).fetchone()
            timeline.append(
                {
                    "report_period": period,
                    "holders": int(n[0]),
                    "adds": int(n[1] or 0),
                    "reduces": int(n[2] or 0),
                }
            )
        return SecurityEvidence(
            key=cusip,
            cusip=cusip,
            issuer=issuer_row[0] if issuer_row else None,
            ticker=str(res.get("symbol", "")) or None,
            resolution_status=str(res.get("status", "UNKNOWN")),
            economic_type=sem.get("economic_type"),
            classification_status=sem.get("classification_status"),
            latest_report_period=latest,
            latest_filing_date=fdate,
            days_since_filing=_days_since(fdate or ""),
            holder_entity_count=holder_entity_count,
            verified_independent_manager_count=independent_count,
            independent_add_manager_count=indep_add,
            independent_reduce_manager_count=indep_reduce,
            independent_new_manager_count=indep_new,
            independent_exit_manager_count=indep_exit,
            activity_counts=activity,
            activity_state=activity_state,
            holders=holders,
            repeated_add_manager_count=rep_add,
            repeated_reduce_manager_count=rep_reduce,
            timeline=timeline,
            quality={
                "resolution_status": str(res.get("status", "UNKNOWN")),
                "economic_type": sem.get("economic_type"),
                "classification_status": sem.get("classification_status"),
            },
        )

    def _activity_state(self, holders, indep_add, indep_reduce) -> str:
        if not holders:
            return "INSUFFICIENT_DATA"
        breadth = len({h["manager_id"] for h in holders if h["change_type"] in ("NEW", "ADD", "REDUCE", "EXIT")})
        if breadth < 2:
            return "LOW_BREADTH"
        if indep_add == 0 and indep_reduce == 0:
            return "NO_RECENT_CHANGE"
        if indep_add > 0 and indep_reduce > 0:
            return "MIXED_ACTIVITY"
        if indep_add > indep_reduce:
            return "MORE_ADDS_THAN_REDUCTIONS"
        return "MORE_REDUCTIONS_THAN_ADDS"

    def _security_repeated(self, cusip: str) -> tuple[int, int]:
        """Count independent managers with >=2 consecutive same-direction
        reported periods for this security (no gap crossing)."""
        return self._repeated_all().get(cusip, (0, 0))

    def _repeated_all(self) -> dict[str, tuple[int, int]]:
        if self._repeated_cache is not None:
            return self._repeated_cache
        qpos = {q: i for i, q in enumerate(self._quarters)}
        rows = self.conn.execute(
            """
            SELECT s.cusip, pc.manager_id, pc.report_period, pc.change_type
            FROM position_changes pc
            JOIN securities s ON s.security_id = pc.security_id
            WHERE pc.put_call=''
            ORDER BY s.cusip, pc.manager_id, pc.report_period
            """
        ).fetchall()
        filed_by_mgr: dict[int, set[str]] = {}
        for r in self.conn.execute(
            "SELECT DISTINCT manager_id, report_period FROM filings WHERE ingest_status='OK'"
        ).fetchall():
            filed_by_mgr.setdefault(int(r[0]), set()).add(r[1])
        result: dict[str, tuple[int, int]] = {}
        cur_key = None
        cur_mgr = None
        prev_period = None
        prev_dir = 0
        run = 0
        best_add = best_reduce = 0
        for cusip, mgr, period, ct in rows:
            mgr = int(mgr)
            key = (cusip, mgr)
            if key != cur_key:
                if cur_key is not None:
                    add_count = 1 if (best_add >= 2 and self._is_independent(cur_mgr)) else 0
                    reduce_count = 1 if (best_reduce >= 2 and self._is_independent(cur_mgr)) else 0
                    c, _ = result.get(cur_key[0], (0, 0))
                    result[cur_key[0]] = (c + add_count, result.get(cur_key[0], (0, 0))[1] + reduce_count)
                cur_key = key
                cur_mgr = mgr
                prev_period = None
                prev_dir = 0
                run = 0
                best_add = best_reduce = 0
            d = _direction(ct)
            filed = filed_by_mgr.get(mgr, set())
            consecutive = (
                prev_period is not None
                and period in filed
                and prev_period in filed
                and qpos.get(period) is not None
                and qpos.get(prev_period) is not None
                and qpos[period] == qpos[prev_period] + 1
            )
            if d != 0 and prev_dir == d and consecutive:
                run += 1
            else:
                run = 1
            if d == 1:
                best_add = max(best_add, run)
            elif d == -1:
                best_reduce = max(best_reduce, run)
            prev_period = period
            prev_dir = d
        if cur_key is not None:
            add_count = 1 if (best_add >= 2 and self._is_independent(cur_mgr)) else 0
            reduce_count = 1 if (best_reduce >= 2 and self._is_independent(cur_mgr)) else 0
            result[cur_key[0]] = (
                result.get(cur_key[0], (0, 0))[0] + add_count,
                result.get(cur_key[0], (0, 0))[1] + reduce_count,
            )
        self._repeated_cache = result
        return result

    # ------------------------------------------------------------------
    # Activity Explorer (neutral)
    # ------------------------------------------------------------------
    def activity_explorer(self, metric: str = "independent_add_manager_count", limit: int = 50) -> list[dict]:
        period = self.latest_period() or ""
        rows = self.conn.execute(
            """
            SELECT s.cusip, pc.change_type, pc.manager_id
            FROM position_changes pc
            JOIN securities s ON s.security_id = pc.security_id
            WHERE pc.report_period=? AND pc.put_call=''
            """,
            (period,),
        ).fetchall()
        indep_add: dict[str, int] = {}
        indep_reduce: dict[str, int] = {}
        indep_new: dict[str, int] = {}
        indep_exit: dict[str, int] = {}
        holder_entity: dict[str, set[int]] = {}
        for cusip, ct, mgr in rows:
            mgr = int(mgr)
            holder_entity.setdefault(cusip, set()).add(mgr)
            if not self._is_independent(mgr):
                continue
            if ct in ("NEW", "ADD"):
                indep_add[cusip] = indep_add.get(cusip, 0) + 1
            if ct in ("REDUCE", "EXIT"):
                indep_reduce[cusip] = indep_reduce.get(cusip, 0) + 1
            if ct == "NEW":
                indep_new[cusip] = indep_new.get(cusip, 0) + 1
            if ct == "EXIT":
                indep_exit[cusip] = indep_exit.get(cusip, 0) + 1
        cusips = set(holder_entity)
        out = []
        for c in cusips:
            rep_add, rep_reduce = self._security_repeated(c)
            res = self._res.get(c, {})
            out.append(
                {
                    "cusip": c,
                    "ticker": res.get("symbol", ""),
                    "issuer": self.conn.execute(
                        "SELECT issuer FROM securities WHERE cusip=?", (c,)
                    ).fetchone()[0] if self.conn.execute(
                        "SELECT 1 FROM securities WHERE cusip=?", (c,)
                    ).fetchone() else None,
                    "resolution_status": res.get("status", "UNKNOWN"),
                    "economic_type": self._sem.get(c, {}).get("economic_type"),
                    "holder_entity_count": len(holder_entity[c]),
                    "independent_add_manager_count": indep_add.get(c, 0),
                    "independent_reduce_manager_count": indep_reduce.get(c, 0),
                    "independent_new_manager_count": indep_new.get(c, 0),
                    "independent_exit_manager_count": indep_exit.get(c, 0),
                    "repeated_add_manager_count": rep_add,
                    "repeated_reduce_manager_count": rep_reduce,
                    "activity_state": (
                        "MORE_ADDS_THAN_REDUCTIONS" if indep_add.get(c, 0) > indep_reduce.get(c, 0)
                        else "MORE_REDUCTIONS_THAN_ADDS" if indep_reduce.get(c, 0) > indep_add.get(c, 0)
                        else "MIXED_ACTIVITY" if (indep_add.get(c, 0) or indep_reduce.get(c, 0))
                        else "NO_RECENT_CHANGE"
                    ),
                }
            )
        metric_map = {
            "independent_add_manager_count": "independent_add_manager_count",
            "independent_reduce_manager_count": "independent_reduce_manager_count",
            "independent_new_manager_count": "independent_new_manager_count",
            "independent_exit_manager_count": "independent_exit_manager_count",
            "repeated_add_manager_count": "repeated_add_manager_count",
            "repeated_reduce_manager_count": "repeated_reduce_manager_count",
            "holder_entity_count": "holder_entity_count",
        }
        key = metric_map.get(metric, "independent_add_manager_count")
        out.sort(key=lambda r: (-int(r[key]), r["cusip"]))
        return out[:limit]

    # ------------------------------------------------------------------
    # My Portfolio (Scenario C)
    # ------------------------------------------------------------------
    def portfolio_evidence(self, portfolio_path: Path | str) -> list[dict] | str:
        p = Path(portfolio_path)
        if not p.exists():
            return "SETUP_REQUIRED"
        rows = []
        with open(p, encoding="utf-8-sig", newline="") as fh:
            import csv

            for r in csv.DictReader(line for line in fh if not line.lstrip().startswith("#")):
                rows.append((str(r.get("ticker", "")).strip().upper(), r.get("weight", "").strip()))
        if not rows:
            return "SETUP_REQUIRED"
        out = []
        for ticker, weight in rows:
            if not ticker:
                continue
            matches = self.security_search(ticker)
            if len(matches) != 1:
                out.append(
                    {
                        "ticker": ticker,
                        "weight": weight,
                        "status": "UNRESOLVED" if not matches else "AMBIGUOUS",
                        "cusip": "",
                        "holder_entity_count": 0,
                        "independent_add_manager_count": 0,
                        "independent_reduce_manager_count": 0,
                        "independent_exit_manager_count": 0,
                        "independent_new_manager_count": 0,
                        "repeated_add_manager_count": 0,
                        "repeated_reduce_manager_count": 0,
                        "activity_state": "INSUFFICIENT_DATA",
                        "days_since_filing": None,
                        "resolution_status": "UNRESOLVED" if not matches else "AMBIGUOUS",
                    }
                )
                continue
            ev = self.security_evidence(matches[0]["cusip"])
            if ev is None:
                continue
            out.append(
                {
                    "ticker": ticker,
                    "weight": weight,
                    "status": "OK",
                    "cusip": ev.cusip,
                    "holder_entity_count": ev.holder_entity_count,
                    "verified_independent_manager_count": ev.verified_independent_manager_count,
                    "independent_add_manager_count": ev.independent_add_manager_count,
                    "independent_reduce_manager_count": ev.independent_reduce_manager_count,
                    "independent_exit_manager_count": ev.independent_exit_manager_count,
                    "independent_new_manager_count": ev.independent_new_manager_count,
                    "repeated_add_manager_count": ev.repeated_add_manager_count,
                    "repeated_reduce_manager_count": ev.repeated_reduce_manager_count,
                    "activity_state": ev.activity_state,
                    "days_since_filing": ev.days_since_filing,
                    "resolution_status": ev.resolution_status,
                }
            )
        return out
