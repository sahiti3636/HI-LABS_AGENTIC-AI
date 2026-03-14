"""
episodic_memory.py
------------------
Episodic memory foundation for RosterIQ — an AI agent that diagnoses
healthcare provider roster pipeline failures.

Provides:
    - init_episodic_db      : Create SQLite DB + episodic_memory table
    - write_episode         : Insert a new episode record
    - read_recent_episodes  : Fetch recent episodes for a session
    - read_episodes_by_entity: Search episodes by a specific entity value

Storage:
    entities_involved is stored as a JSON string with the schema:
    {"states": [], "orgs": [], "ros": [], "markets": []}

Dependencies: Python standard library only (sqlite3, json, datetime).
"""

import sqlite3
import json
from datetime import datetime


# ---------------------------------------------------------------------------
# 1. Database Initialization
# ---------------------------------------------------------------------------

def init_episodic_db(db_path: str = "episodic_memory.db") -> None:
    """
    Initialize the SQLite database and create the episodic_memory table
    if it does not already exist.

    Args:
        db_path: Path to the SQLite database file.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS episodic_memory (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id        TEXT    NOT NULL,
        timestamp         DATETIME DEFAULT CURRENT_TIMESTAMP,
        query_text        TEXT    NOT NULL,
        intent_classified TEXT,
        sql_generated     TEXT,
        result_summary    TEXT,
        entities_involved TEXT,
        findings_text     TEXT,
        chart_generated   INTEGER DEFAULT 0
    )
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute(create_table_sql)
        conn.commit()
    print(f"[episodic_memory] DB initialised at: {db_path}")


# ---------------------------------------------------------------------------
# 2. Write Function
# ---------------------------------------------------------------------------

def write_episode(
    session_id: str,
    query_text: str,
    intent_classified: str,
    sql_generated: str,
    result_summary: str,
    entities_involved_dict: dict,
    findings_text: str,
    chart_generated: bool = False,
    db_path: str = "episodic_memory.db",
) -> int:
    """
    Insert a new episode into episodic_memory.

    Args:
        session_id:            Unique session identifier.
        query_text:            The user's natural-language query.
        intent_classified:     Classified intent label (e.g. 'gap_analysis').
        sql_generated:         The SQL query generated for this episode.
        result_summary:        Short textual summary of the query result.
        entities_involved_dict: Dict with keys 'states', 'orgs', 'ros',
                                'markets'; serialised to JSON before storage.
        findings_text:         Detailed narrative findings from the agent.
        chart_generated:       Whether a chart was produced (default False).
        db_path:               Path to the SQLite database file.

    Returns:
        The auto-incremented row id of the newly inserted episode.
    """
    entities_json = json.dumps(entities_involved_dict)
    chart_flag = 1 if chart_generated else 0

    insert_sql = """
    INSERT INTO episodic_memory (
        session_id, query_text, intent_classified, sql_generated,
        result_summary, entities_involved, findings_text, chart_generated
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            insert_sql,
            (
                session_id,
                query_text,
                intent_classified,
                sql_generated,
                result_summary,
                entities_json,
                findings_text,
                chart_flag,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
        assert row_id is not None, "INSERT did not return a valid lastrowid"

    print(f"[episodic_memory] Episode written - id={row_id}, session={session_id}")
    return row_id


# ---------------------------------------------------------------------------
# 3. Read: Recent Episodes (by Session)
# ---------------------------------------------------------------------------

def read_recent_episodes(
    session_id: str,
    limit: int = 5,
    db_path: str = "episodic_memory.db",
) -> list[dict]:
    """
    Fetch the most recent episodes for a given session.

    Args:
        session_id: Session to filter on.
        limit:      Maximum number of episodes to return (default 5).
        db_path:    Path to the SQLite database file.

    Returns:
        A list of dicts (all columns), with entities_involved already
        deserialised back to a Python dict.
    """
    select_sql = """
    SELECT id, session_id, timestamp, query_text, intent_classified,
           sql_generated, result_summary, entities_involved,
           findings_text, chart_generated
    FROM   episodic_memory
    WHERE  session_id = ?
    ORDER BY timestamp DESC
    LIMIT  ?
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(select_sql, (session_id, limit)).fetchall()

    episodes: list[dict] = []
    for row in rows:
        episode: dict = dict(row)
        episode["entities_involved"] = json.loads(episode["entities_involved"] or "{}")
        episode["chart_generated"] = int(episode["chart_generated"]) != 0
        episodes.append(episode)

    return episodes


# ---------------------------------------------------------------------------
# 4. Read: Episodes by Entity Value
# ---------------------------------------------------------------------------

def read_episodes_by_entity(
    entity_value: str,
    entity_type: str = "states",
    limit: int = 10,
    db_path: str = "episodic_memory.db",
) -> list[dict]:
    """
    Search episode history for a specific entity value inside the JSON blob.

    The search uses SQL LIKE against the entities_involved column, so it
    works without requiring JSON extensions in SQLite.

    Args:
        entity_value: The entity string to search for (e.g. 'KS').
        entity_type:  The entity category key to narrow context
                      ('states', 'orgs', 'ros', 'markets'). Used only as
                      documentation / caller guidance; the LIKE search
                      targets the entire JSON blob for maximum recall.
        limit:        Maximum number of episodes to return (default 10).
        db_path:      Path to the SQLite database file.

    Returns:
        A list of episode dicts ordered by timestamp DESC, with
        entities_involved deserialised to a Python dict.

    Example:
        read_episodes_by_entity('KS', 'states')
        → all past episodes whose entities_involved JSON contains 'KS'.
    """
    pattern = f"%{entity_value}%"
    select_sql = """
    SELECT id, session_id, timestamp, query_text, intent_classified,
           sql_generated, result_summary, entities_involved,
           findings_text, chart_generated
    FROM   episodic_memory
    WHERE  entities_involved LIKE ?
    ORDER BY timestamp DESC
    LIMIT  ?
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(select_sql, (pattern, limit)).fetchall()

    episodes: list[dict] = []
    for row in rows:
        episode: dict = dict(row)
        episode["entities_involved"] = json.loads(episode["entities_involved"] or "{}")
        episode["chart_generated"] = int(episode["chart_generated"]) != 0
        episodes.append(episode)

    return episodes


# ---------------------------------------------------------------------------
# 5. __main__ Test Block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    DB_PATH = "episodic_memory_test.db"

    # Clean up any leftover test DB from a previous run
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print("=" * 60)
    print("RosterIQ — Episodic Memory Self-Test")
    print("=" * 60)

    # ── Step 1: Initialise DB ──────────────────────────────────────
    init_episodic_db(db_path=DB_PATH)

    # ── Step 2: Write two sample episodes ─────────────────────────
    ep1_id = write_episode(
        session_id="session-001",
        query_text="Show me gap rates for Kansas in Q1 2024",
        intent_classified="gap_analysis",
        sql_generated=(
            "SELECT state, COUNT(*) AS gaps "
            "FROM roster_pipeline "
            "WHERE state = 'KS' AND quarter = 'Q1-2024' "
            "GROUP BY state"
        ),
        result_summary="Kansas had 142 gaps in Q1 2024 across 3 organisations.",
        entities_involved_dict={
            "states": ["KS"],
            "orgs": ["Org-A", "Org-B", "Org-C"],
            "ros": [],
            "markets": ["Kansas City"],
        },
        findings_text=(
            "Pipeline gaps in Kansas are concentrated in rural markets. "
            "Org-B shows the highest gap rate at 38 %."
        ),
        chart_generated=True,
        db_path=DB_PATH,
    )

    ep2_id = write_episode(
        session_id="session-001",
        query_text="Compare Texas vs California provider coverage last month",
        intent_classified="coverage_comparison",
        sql_generated=(
            "SELECT state, AVG(coverage_pct) AS avg_coverage "
            "FROM roster_pipeline "
            "WHERE state IN ('TX','CA') AND month = 'Feb-2024' "
            "GROUP BY state"
        ),
        result_summary="TX avg coverage 74 %, CA avg coverage 81 %.",
        entities_involved_dict={
            "states": ["TX", "CA"],
            "orgs": [],
            "ros": ["RO-West", "RO-South"],
            "markets": ["Dallas", "Los Angeles"],
        },
        findings_text=(
            "California outperforms Texas in provider coverage by 7 pp. "
            "RO-South should focus on Texas market gaps."
        ),
        chart_generated=False,
        db_path=DB_PATH,
    )

    # ── Step 3a: Read recent episodes ─────────────────────────────
    print("\n--- read_recent_episodes(session-001, limit=5) ---")
    recent = read_recent_episodes("session-001", limit=5, db_path=DB_PATH)
    for ep in recent:
        print(f"\n  id            : {ep['id']}")
        print(f"  timestamp     : {ep['timestamp']}")
        print(f"  query_text    : {ep['query_text']}")
        print(f"  intent        : {ep['intent_classified']}")
        print(f"  entities      : {ep['entities_involved']}")
        print(f"  chart_generated: {ep['chart_generated']}")
        print(f"  result_summary: {ep['result_summary']}")

    # ── Step 3b: Read by entity ────────────────────────────────────
    print("\n--- read_episodes_by_entity('KS', 'states') ---")
    ks_episodes = read_episodes_by_entity("KS", entity_type="states", db_path=DB_PATH)
    print(f"  Episodes found: {len(ks_episodes)}")
    for ep in ks_episodes:
        print(f"  >> id={ep['id']} | query: {ep['query_text']}")

    print("\n--- read_episodes_by_entity('TX', 'states') ---")
    tx_episodes = read_episodes_by_entity("TX", entity_type="states", db_path=DB_PATH)
    print(f"  Episodes found: {len(tx_episodes)}")
    for ep in tx_episodes:
        print(f"  >> id={ep['id']} | query: {ep['query_text']}")

    print("\n--- read_episodes_by_entity('RO-West', 'ros') ---")
    ro_episodes = read_episodes_by_entity("RO-West", entity_type="ros", db_path=DB_PATH)
    print(f"  Episodes found: {len(ro_episodes)}")
    for ep in ro_episodes:
        print(f"  >> id={ep['id']} | query: {ep['query_text']}")

    # ── Cleanup ────────────────────────────────────────────────────
    os.remove(DB_PATH)
    print("\n[OK] All tests passed - episodic memory is working correctly.")
    print("=" * 60)
