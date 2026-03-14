"""
RosterIQ Data Loader
Loads CSVs into an in-memory SQLite database with dynamic schema introspection.
"""

import os
import sqlite3
import hashlib
import pandas as pd
from typing import Optional

from rosteriq.config import DATA_DIR, TABLE_MAP, SQLITE_DB

# Module-level connection
_conn: Optional[sqlite3.Connection] = None
_file_hashes: dict[str, str] = {}


def _hash_file(path: str) -> str:
    """Compute MD5 hash of a file for dirty-flag detection."""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def get_connection() -> sqlite3.Connection:
    """Return the shared SQLite connection, loading data if needed."""
    global _conn
    if _conn is None:
        _conn = _load_all()
    return _conn


def _load_all() -> sqlite3.Connection:
    """Load all CSVs into a fresh SQLite in-memory database."""
    global _file_hashes
    conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    for csv_file, table_name in TABLE_MAP.items():
        csv_path = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(csv_path):
            print(f'[loader] WARNING: {csv_path} not found, skipping.')
            continue

        _file_hashes[csv_file] = _hash_file(csv_path)
        df = pd.read_csv(csv_path, low_memory=False)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        print(f'[loader] Loaded {table_name}: {len(df)} rows x {len(df.columns)} cols')

    return conn


def reload_if_changed() -> bool:
    """
    Check file hashes and reload only if any CSV changed.
    Returns True if a reload was performed.
    """
    global _conn, _file_hashes
    changed = False

    for csv_file in TABLE_MAP:
        csv_path = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(csv_path):
            continue
        current_hash = _hash_file(csv_path)
        if _file_hashes.get(csv_file) != current_hash:
            changed = True
            break

    if changed:
        if _conn:
            _conn.close()
        _conn = _load_all()
        return True

    return False


def get_schema() -> dict[str, list[dict]]:
    """
    Return all table schemas via dynamic introspection.
    Returns: {table_name: [{name, type, notnull, pk}, ...]}
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    schema = {}
    for table in tables:
        cursor.execute(f'PRAGMA table_info("{table}")')
        cols = []
        for row in cursor.fetchall():
            cols.append({
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'pk': bool(row[5]),
            })
        schema[table] = cols

    return schema


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a read query and return results as list of dicts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute a read query and return results as a DataFrame."""
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)
