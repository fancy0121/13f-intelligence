"""SQLite persistence for 13F normalized data.

Schema version is recorded in schema_version; migrations apply sequentially.
All ingestion writes are idempotent: re-running with the same raw data yields
the same database content (same checksums for analyzed tables).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 3

DDL = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at_utc TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS managers (
        manager_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        cik INTEGER NOT NULL UNIQUE,
        strategy_type TEXT,
        signal_quality REAL,
        replicability_score REAL,
        turnover_class TEXT,
        concentration_class TEXT,
        passive_exposure INTEGER NOT NULL DEFAULT 0,
        derivatives_dependence TEXT,
        representativeness TEXT,
        investment_horizon TEXT,
        scoring_status TEXT NOT NULL DEFAULT 'NOT_APPROVED',
        active INTEGER NOT NULL DEFAULT 1,
        methodology_version TEXT,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS filings (
        filing_id INTEGER PRIMARY KEY,
        manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
        report_period TEXT NOT NULL,
        filing_date TEXT NOT NULL,
        accession_number TEXT NOT NULL UNIQUE,
        form_type TEXT NOT NULL,
        is_amendment INTEGER NOT NULL DEFAULT 0,
        accepted_at TEXT,
        amendment_number INTEGER
            CHECK(amendment_number IS NULL OR amendment_number >= 1),
        amendment_type TEXT
            CHECK(amendment_type IS NULL OR amendment_type IN (
                'RESTATEMENT', 'ADD_NEW_HOLDINGS'
            )),
        amendment_status TEXT NOT NULL DEFAULT 'NOT_APPLICABLE'
            CHECK(amendment_status IN (
                'NOT_APPLICABLE', 'PARSED', 'AMENDMENT_PENDING'
            )),
        amends_filing_id INTEGER REFERENCES filings(filing_id),
        source_url TEXT NOT NULL,
        raw_checksum TEXT NOT NULL,
        raw_path TEXT NOT NULL,
        cover_checksum TEXT,
        cover_raw_path TEXT,
        fetched_at_utc TEXT,
        ingest_status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS holdings (
        holding_id INTEGER PRIMARY KEY,
        filing_id INTEGER NOT NULL REFERENCES filings(filing_id),
        manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
        report_period TEXT NOT NULL,
        row_ordinal INTEGER NOT NULL,
        cusip TEXT NOT NULL,
        ticker TEXT,
        issuer TEXT NOT NULL,
        title_of_class TEXT NOT NULL,
        security_class TEXT,
        put_call TEXT NOT NULL DEFAULT ''
            CHECK(put_call IN ('', 'CALL', 'PUT')),
        ssh_prnamt_type TEXT
            CHECK(ssh_prnamt_type IS NULL OR ssh_prnamt_type IN ('SH', 'PRN')),
        investment_discretion TEXT,
        other_manager TEXT,
        shares INTEGER CHECK(shares IS NULL OR shares >= 0),
        value INTEGER CHECK(value IS NULL OR value >= 0),
        portfolio_weight REAL,
        UNIQUE(filing_id, row_ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS securities (
        security_id INTEGER PRIMARY KEY,
        cusip TEXT NOT NULL UNIQUE,
        ticker TEXT,
        issuer TEXT,
        share_class TEXT,
        mapping_status TEXT NOT NULL,
        mapping_source TEXT NOT NULL,
        mapping_date TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mapping_history (
        mapping_history_id INTEGER PRIMARY KEY,
        security_id INTEGER NOT NULL REFERENCES securities(security_id),
        cusip TEXT NOT NULL,
        ticker TEXT,
        mapping_status TEXT NOT NULL,
        mapping_source TEXT NOT NULL,
        effective_date TEXT NOT NULL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS position_changes (
        change_id INTEGER PRIMARY KEY,
        manager_id INTEGER NOT NULL,
        security_id INTEGER NOT NULL,
        report_period TEXT NOT NULL,
        put_call TEXT NOT NULL DEFAULT '',
        shares_type TEXT NOT NULL,
        change_type TEXT NOT NULL,
        shares_prev INTEGER,
        shares_now INTEGER,
        share_change INTEGER,
        share_change_pct REAL,
        weight_prev REAL,
        weight_now REAL,
        weight_change REAL,
        methodology_version TEXT NOT NULL,
        UNIQUE(
            manager_id, security_id, put_call, shares_type, report_period,
            methodology_version
        ),
        CHECK(put_call IN ('', 'CALL', 'PUT')),
        CHECK(shares_type IN ('SH', 'PRN'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consensus_scores (
        consensus_id INTEGER PRIMARY KEY,
        security_id INTEGER NOT NULL,
        report_period TEXT NOT NULL,
        put_call TEXT NOT NULL DEFAULT '',
        shares_type TEXT NOT NULL,
        manager_count INTEGER NOT NULL,
        high_quality_manager_count INTEGER,
        independent_strategy_count INTEGER,
        raw_contributions TEXT NOT NULL,
        consensus_score REAL NOT NULL,
        methodology_version TEXT NOT NULL,
        UNIQUE(
            security_id, put_call, shares_type, report_period,
            methodology_version
        ),
        CHECK(put_call IN ('', 'CALL', 'PUT')),
        CHECK(shares_type IN ('SH', 'PRN'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trends (
        trend_id INTEGER PRIMARY KEY,
        security_id INTEGER NOT NULL,
        report_period TEXT NOT NULL,
        put_call TEXT NOT NULL DEFAULT '',
        shares_type TEXT NOT NULL,
        horizon TEXT NOT NULL,
        trend_label TEXT NOT NULL,
        trend_score REAL,
        methodology_version TEXT NOT NULL,
        UNIQUE(
            security_id, put_call, shares_type, report_period, horizon,
            methodology_version
        ),
        CHECK(put_call IN ('', 'CALL', 'PUT')),
        CHECK(shares_type IN ('SH', 'PRN'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS effective_periods (
        effective_period_id INTEGER PRIMARY KEY,
        manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
        report_period TEXT NOT NULL,
        methodology_version TEXT NOT NULL,
        state_hash TEXT NOT NULL,
        status TEXT NOT NULL
            CHECK(status IN ('READY', 'AMENDMENT_PENDING', 'INCOMPLETE')),
        total_value INTEGER CHECK(total_value IS NULL OR total_value >= 0),
        UNIQUE(manager_id, report_period, methodology_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS effective_filing_components (
        effective_period_id INTEGER NOT NULL
            REFERENCES effective_periods(effective_period_id) ON DELETE CASCADE,
        filing_id INTEGER NOT NULL REFERENCES filings(filing_id),
        component_role TEXT NOT NULL
            CHECK(component_role IN ('BASE', 'SUPPLEMENT')),
        sequence INTEGER NOT NULL CHECK(sequence >= 0),
        PRIMARY KEY(effective_period_id, filing_id),
        UNIQUE(effective_period_id, sequence)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS effective_positions (
        effective_position_id INTEGER PRIMARY KEY,
        effective_period_id INTEGER NOT NULL
            REFERENCES effective_periods(effective_period_id) ON DELETE CASCADE,
        manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
        report_period TEXT NOT NULL,
        security_id INTEGER NOT NULL REFERENCES securities(security_id),
        put_call TEXT NOT NULL DEFAULT ''
            CHECK(put_call IN ('', 'CALL', 'PUT')),
        shares_type TEXT NOT NULL CHECK(shares_type IN ('SH', 'PRN')),
        shares INTEGER NOT NULL CHECK(shares >= 0),
        value INTEGER NOT NULL CHECK(value >= 0),
        portfolio_weight REAL NOT NULL
            CHECK(portfolio_weight >= 0 AND portfolio_weight <= 1),
        provenance_json TEXT NOT NULL,
        UNIQUE(effective_period_id, security_id, put_call, shares_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quality_events (
        event_id INTEGER PRIMARY KEY,
        event_type TEXT NOT NULL,
        manager_id INTEGER,
        report_period TEXT,
        filing_id INTEGER,
        severity TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at_utc TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_filings_manager_period
        ON filings(manager_id, report_period)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_holdings_manager_period
        ON holdings(manager_id, report_period)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_holdings_cusip
        ON holdings(cusip)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_holdings_filing
        ON holdings(filing_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_position_changes_mgr_sec
        ON position_changes(manager_id, security_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_position_changes_period
        ON position_changes(report_period)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_securities_ticker
        ON securities(ticker)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_effective_periods_manager_period
        ON effective_periods(manager_id, report_period)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_effective_positions_security_period
        ON effective_positions(security_id, report_period)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_effective_positions_manager_period
        ON effective_positions(manager_id, report_period)
    """,
]


def connect(db_path: Path | str) -> sqlite3.Connection:
    # check_same_thread=False: ProductStore is cached via streamlit.cache_resource
    # and reused across script-runner threads (read-only UI access).
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def connect_readonly(
    db_path: Path | str,
    *,
    immutable: bool = False,
) -> sqlite3.Connection:
    """Open an existing SQLite database without any write capability."""

    path = Path(db_path).resolve()
    query = "mode=ro"
    if immutable:
        query += "&immutable=1"
    conn = sqlite3.connect(
        f"{path.as_uri()}?{query}",
        uri=True,
        check_same_thread=False,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA query_only = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("SAVEPOINT init_db")
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at_utc TEXT NOT NULL
            )
            """
        )
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current = row[0] if row and row[0] is not None else 0
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema {current} is newer than supported "
                f"{SCHEMA_VERSION}"
            )
        if 0 < current < SCHEMA_VERSION:
            _migrate_to_v3(conn)
        for ddl in DDL:
            conn.execute(ddl)
        if current < SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version, applied_at_utc) "
                "VALUES (?, datetime('now'))",
                (SCHEMA_VERSION,),
            )
        conn.execute("RELEASE SAVEPOINT init_db")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT init_db")
        conn.execute("RELEASE SAVEPOINT init_db")
        raise


def _migrate_to_v3(conn: sqlite3.Connection) -> None:
    """Migrate schema v1/v2 without fabricating missing SEC semantics.

    Raw filing and holding rows are retained. Existing derived analytics are
    deliberately cleared because the old keys omitted shares type and the old
    amendment selection could be incorrect; they are reproducible from raw
    evidence after cover metadata is normalized.
    """

    _add_column_if_missing(conn, "filings", "accepted_at", "TEXT")
    _add_column_if_missing(
        conn,
        "filings",
        "amendment_number",
        "INTEGER CHECK(amendment_number IS NULL OR amendment_number >= 1)",
    )
    _add_column_if_missing(
        conn,
        "filings",
        "amendment_type",
        "TEXT CHECK(amendment_type IS NULL OR amendment_type IN "
        "('RESTATEMENT', 'ADD_NEW_HOLDINGS'))",
    )
    _add_column_if_missing(conn, "filings", "amendment_status", "TEXT")
    _add_column_if_missing(conn, "filings", "cover_checksum", "TEXT")
    _add_column_if_missing(conn, "filings", "cover_raw_path", "TEXT")
    _add_column_if_missing(
        conn,
        "holdings",
        "ssh_prnamt_type",
        "TEXT CHECK(ssh_prnamt_type IS NULL OR ssh_prnamt_type IN ('SH', 'PRN'))",
    )
    _add_column_if_missing(conn, "holdings", "investment_discretion", "TEXT")
    _add_column_if_missing(conn, "holdings", "other_manager", "TEXT")

    conn.execute(
        """
        UPDATE filings
        SET amendment_status = CASE
            WHEN is_amendment = 1 THEN 'AMENDMENT_PENDING'
            ELSE 'NOT_APPLICABLE'
        END
        WHERE amendment_status IS NULL OR amendment_status = ''
        """
    )

    for table in (
        "effective_positions",
        "effective_filing_components",
        "effective_periods",
        "trends",
        "consensus_scores",
        "position_changes",
    ):
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    if column not in columns:
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {declaration}')


def upsert_manager(
    conn: sqlite3.Connection,
    *,
    name: str,
    cik: int,
    notes: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO managers(name, cik, notes)
        VALUES (?, ?, ?)
        ON CONFLICT(cik) DO UPDATE SET name=excluded.name, notes=excluded.notes
        """,
        (name, cik, notes),
    )
    conn.commit()
    row = conn.execute("SELECT manager_id FROM managers WHERE cik=?", (cik,)).fetchone()
    return row[0]


def upsert_filing(
    conn: sqlite3.Connection,
    *,
    manager_id: int,
    report_period: str,
    filing_date: str,
    accession_number: str,
    form_type: str,
    is_amendment: bool,
    source_url: str,
    raw_checksum: str,
    raw_path: str,
    fetched_at_utc: str | None,
    ingest_status: str,
    accepted_at: str | None = None,
    amendment_number: int | None = None,
    amendment_type: str | None = None,
    amendment_status: str | None = None,
    amends_filing_id: int | None = None,
    cover_checksum: str | None = None,
    cover_raw_path: str | None = None,
) -> int:
    if hasattr(amendment_type, "value"):
        amendment_type = amendment_type.value
    if amendment_status is None:
        amendment_status = (
            "AMENDMENT_PENDING" if is_amendment else "NOT_APPLICABLE"
        )
    conn.execute(
        """
        INSERT INTO filings(
            manager_id, report_period, filing_date, accession_number, form_type,
            is_amendment, accepted_at, amendment_number, amendment_type,
            amendment_status, amends_filing_id, source_url, raw_checksum,
            raw_path, cover_checksum, cover_raw_path, fetched_at_utc,
            ingest_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(accession_number) DO UPDATE SET
            ingest_status=excluded.ingest_status,
            raw_checksum=excluded.raw_checksum,
            raw_path=excluded.raw_path,
            fetched_at_utc=excluded.fetched_at_utc,
            accepted_at=excluded.accepted_at,
            amendment_number=excluded.amendment_number,
            amendment_type=excluded.amendment_type,
            amendment_status=excluded.amendment_status,
            amends_filing_id=excluded.amends_filing_id,
            cover_checksum=excluded.cover_checksum,
            cover_raw_path=excluded.cover_raw_path
        """,
        (
            manager_id,
            report_period,
            filing_date,
            accession_number,
            form_type,
            int(is_amendment),
            accepted_at,
            amendment_number,
            amendment_type,
            amendment_status,
            amends_filing_id,
            source_url,
            raw_checksum,
            raw_path,
            cover_checksum,
            cover_raw_path,
            fetched_at_utc,
            ingest_status,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT filing_id FROM filings WHERE accession_number=?", (accession_number,)
    ).fetchone()
    return row[0]


def replace_holdings(
    conn: sqlite3.Connection,
    *,
    filing_id: int,
    manager_id: int,
    report_period: str,
    rows,
    commit: bool = True,
) -> None:
    """Replace all holdings rows for a filing (idempotent by filing_id)."""
    conn.execute("DELETE FROM holdings WHERE filing_id=?", (filing_id,))
    for row in rows:
        conn.execute(
            """
            INSERT INTO holdings(
                filing_id, manager_id, report_period, row_ordinal, cusip,
                ticker, issuer, title_of_class, security_class, put_call,
                ssh_prnamt_type, investment_discretion, other_manager,
                shares, value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filing_id,
                manager_id,
                report_period,
                row.row_ordinal,
                row.cusip,
                None,  # ticker resolved later via security_master
                row.name_of_issuer,
                row.title_of_class,
                None,
                row.put_call,
                getattr(row, "ssh_prnamt_type", None),
                getattr(row, "investment_discretion", None),
                getattr(row, "other_manager", None),
                row.shares,
                row.value,
            ),
        )
    if commit:
        conn.commit()


def ensure_security(
    conn: sqlite3.Connection,
    *,
    cusip: str,
    ticker: str | None,
    issuer: str | None,
    share_class: str | None,
    mapping_status: str,
    mapping_source: str,
    mapping_date: str,
    commit: bool = True,
) -> int:
    conn.execute(
        """
        INSERT INTO securities(
            cusip, ticker, issuer, share_class, mapping_status, mapping_source,
            mapping_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cusip) DO UPDATE SET
            ticker=COALESCE(excluded.ticker, securities.ticker),
            issuer=COALESCE(excluded.issuer, securities.issuer),
            share_class=COALESCE(excluded.share_class, securities.share_class),
            mapping_status=CASE
                WHEN securities.mapping_status='UNRESOLVED'
                THEN excluded.mapping_status
                ELSE securities.mapping_status END,
            mapping_source=CASE
                WHEN securities.mapping_status='UNRESOLVED'
                THEN excluded.mapping_source
                ELSE securities.mapping_source END,
            mapping_date=excluded.mapping_date
        """,
        (cusip, ticker, issuer, share_class, mapping_status, mapping_source, mapping_date),
    )
    if commit:
        conn.commit()
    row = conn.execute("SELECT security_id FROM securities WHERE cusip=?", (cusip,)).fetchone()
    return row[0]


def bulk_ensure_securities(
    conn: sqlite3.Connection,
    rows: list[tuple],
    *,
    mapping_date: str,
    commit: bool = True,
) -> None:
    """Batch upsert securities.

    rows: list of (cusip, ticker, issuer, share_class, mapping_status,
    mapping_source). Uses INSERT ... ON CONFLICT DO UPDATE with the same
    COALESCE/CASE semantics as ensure_security.
    """
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO securities(
            cusip, ticker, issuer, share_class, mapping_status, mapping_source,
            mapping_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cusip) DO UPDATE SET
            ticker=COALESCE(excluded.ticker, securities.ticker),
            issuer=COALESCE(excluded.issuer, securities.issuer),
            share_class=COALESCE(excluded.share_class, securities.share_class),
            mapping_status=CASE
                WHEN securities.mapping_status='UNRESOLVED'
                THEN excluded.mapping_status
                ELSE securities.mapping_status END,
            mapping_source=CASE
                WHEN securities.mapping_status='UNRESOLVED'
                THEN excluded.mapping_source
                ELSE securities.mapping_source END,
            mapping_date=excluded.mapping_date
        """,
        [
            (c, t, i, s, st, src, mapping_date)
            for (c, t, i, s, st, src) in rows
        ],
    )
    if commit:
        conn.commit()


def set_holding_ticker(
    conn: sqlite3.Connection,
    *,
    filing_id: int,
    cusip: str,
    ticker: str | None,
    commit: bool = True,
) -> None:
    conn.execute(
        "UPDATE holdings SET ticker=? WHERE filing_id=? AND cusip=?",
        (ticker, filing_id, cusip),
    )
    if commit:
        conn.commit()


def backfill_holding_tickers(
    conn: sqlite3.Connection,
    *,
    filing_id: int,
    commit: bool = True,
) -> None:
    """Set holdings.ticker from securities in one UPDATE (no per-row loop)."""
    conn.execute(
        """
        UPDATE holdings
        SET ticker = (
            SELECT securities.ticker
            FROM securities
            WHERE securities.cusip = holdings.cusip
        )
        WHERE filing_id = ?
        """,
        (filing_id,),
    )
    if commit:
        conn.commit()


def add_quality_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    severity: str,
    message: str,
    manager_id: int | None = None,
    report_period: str | None = None,
    filing_id: int | None = None,
    commit: bool = True,
) -> None:
    conn.execute(
        """
        INSERT INTO quality_events(
            event_type, manager_id, report_period, filing_id, severity,
            message, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (event_type, manager_id, report_period, filing_id, severity, message),
    )
    if commit:
        conn.commit()
