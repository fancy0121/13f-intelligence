from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thirteenf.database import SCHEMA_VERSION, connect, init_db


def _create_schema_v2(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at_utc TEXT NOT NULL);
        INSERT INTO schema_version VALUES(2, '2026-08-24T00:00:00Z');

        CREATE TABLE managers(
            manager_id INTEGER PRIMARY KEY, name TEXT NOT NULL, cik INTEGER NOT NULL UNIQUE
        );
        INSERT INTO managers VALUES(1, 'TEST MANAGER', 1);

        CREATE TABLE filings(
            filing_id INTEGER PRIMARY KEY,
            manager_id INTEGER NOT NULL,
            report_period TEXT NOT NULL,
            filing_date TEXT NOT NULL,
            accession_number TEXT NOT NULL UNIQUE,
            form_type TEXT NOT NULL,
            is_amendment INTEGER NOT NULL DEFAULT 0,
            amends_filing_id INTEGER,
            source_url TEXT NOT NULL,
            raw_checksum TEXT NOT NULL,
            raw_path TEXT NOT NULL,
            fetched_at_utc TEXT,
            ingest_status TEXT NOT NULL
        );
        INSERT INTO filings VALUES
          (1,1,'2026-06-30','2026-08-14','BASE','13F-HR',0,NULL,'https://sec/base','a','raw/base',NULL,'OK'),
          (2,1,'2026-06-30','2026-08-20','AMEND','13F-HR/A',1,NULL,'https://sec/amend','b','raw/amend',NULL,'OK');

        CREATE TABLE holdings(
            holding_id INTEGER PRIMARY KEY,
            filing_id INTEGER NOT NULL,
            manager_id INTEGER NOT NULL,
            report_period TEXT NOT NULL,
            row_ordinal INTEGER NOT NULL,
            cusip TEXT NOT NULL,
            ticker TEXT,
            issuer TEXT NOT NULL,
            title_of_class TEXT NOT NULL,
            security_class TEXT,
            put_call TEXT NOT NULL DEFAULT '',
            shares REAL,
            value INTEGER,
            portfolio_weight REAL,
            UNIQUE(filing_id, row_ordinal)
        );
        INSERT INTO holdings(
            holding_id, filing_id, manager_id, report_period, row_ordinal,
            cusip, issuer, title_of_class, shares, value
        ) VALUES
          (1,1,1,'2026-06-30',1,'123456789','ISSUER','COM',10,100),
          (2,2,1,'2026-06-30',1,'123456789','ISSUER','COM',20,200);

        CREATE TABLE position_changes(
            change_id INTEGER PRIMARY KEY, manager_id INTEGER, security_id INTEGER,
            report_period TEXT, put_call TEXT, methodology_version TEXT
        );
        INSERT INTO position_changes VALUES(1,1,1,'2026-06-30','','0.1.0');
        CREATE TABLE consensus_scores(
            consensus_id INTEGER PRIMARY KEY, security_id INTEGER,
            report_period TEXT, put_call TEXT, methodology_version TEXT
        );
        INSERT INTO consensus_scores VALUES(1,1,'2026-06-30','','0.1.0');
        CREATE TABLE trends(
            trend_id INTEGER PRIMARY KEY, security_id INTEGER, report_period TEXT,
            put_call TEXT, horizon TEXT, methodology_version TEXT
        );
        INSERT INTO trends VALUES(1,1,'2026-06-30','','1Q','0.1.0');
        """
    )
    conn.commit()
    conn.close()


def test_v2_migration_preserves_raw_rows_and_marks_amendment_pending(tmp_path):
    path = tmp_path / "v2.db"
    _create_schema_v2(path)

    conn = connect(path)
    init_db(conn)

    assert conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0] == 2
    raw = conn.execute(
        """
        SELECT ssh_prnamt_type, investment_discretion, other_manager
        FROM holdings ORDER BY holding_id
        """
    ).fetchall()
    assert [tuple(row) for row in raw] == [(None, None, None), (None, None, None)]

    filings = conn.execute(
        """
        SELECT accession_number, amendment_number, amendment_type,
               amendment_status, amends_filing_id
        FROM filings ORDER BY filing_id
        """
    ).fetchall()
    assert tuple(filings[0]) == ("BASE", None, None, "NOT_APPLICABLE", None)
    assert tuple(filings[1]) == ("AMEND", None, None, "AMENDMENT_PENDING", None)
    assert conn.execute("SELECT COUNT(*) FROM effective_periods").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM position_changes").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM consensus_scores").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM trends").fetchone()[0] == 0
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == SCHEMA_VERSION

    init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0] == 2
    conn.close()
