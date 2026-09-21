"""Semantic comparison for independently rebuilt SQLite databases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from thirteenf.database import connect_readonly


_VOLATILE_COLUMNS = {"applied_at_utc", "created_at_utc"}


@dataclass(frozen=True)
class DatabaseComparison:
    matches: bool
    different_tables: tuple[str, ...]
    first_hashes: dict[str, str]
    second_hashes: dict[str, str]


def compare_databases(
    first: Path | str,
    second: Path | str,
) -> DatabaseComparison:
    """Compare all user tables while excluding only documented timestamps."""

    first_hashes = semantic_table_hashes(first)
    second_hashes = semantic_table_hashes(second)
    tables = sorted(set(first_hashes) | set(second_hashes))
    different = tuple(
        table for table in tables if first_hashes.get(table) != second_hashes.get(table)
    )
    return DatabaseComparison(
        matches=not different,
        different_tables=different,
        first_hashes=first_hashes,
        second_hashes=second_hashes,
    )


def semantic_table_hashes(path: Path | str) -> dict[str, str]:
    conn = connect_readonly(path, immutable=True)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {table: _table_hash(conn, table) for table in tables}
    finally:
        conn.close()


def _table_hash(conn: sqlite3.Connection, table: str) -> str:
    table_literal = table.replace('"', '""')
    columns = [
        row[1]
        for row in conn.execute(f'PRAGMA table_info("{table_literal}")')
        if row[1] not in _VOLATILE_COLUMNS
    ]
    if not columns:
        payload = {"columns": [], "rows": []}
    else:
        quoted = [f'"{name.replace(chr(34), chr(34) * 2)}"' for name in columns]
        projection = ", ".join(quoted)
        ordering = ", ".join(quoted)
        rows = [
            [_json_value(value) for value in row]
            for row in conn.execute(
                f'SELECT {projection} FROM "{table_literal}" ORDER BY {ordering}'
            )
        ]
        payload = {"columns": columns, "rows": rows}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_value(value):
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first")
    parser.add_argument("second")
    args = parser.parse_args(argv)
    result = compare_databases(args.first, args.second)
    print(
        json.dumps(
            {
                "matches": result.matches,
                "different_tables": list(result.different_tables),
            },
            sort_keys=True,
        )
    )
    return 0 if result.matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
