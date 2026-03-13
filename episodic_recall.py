"""
episodic_recall.py
------------------
Unified episodic recall layer for RosterIQ.

Combines SQLite structured recall (episodic_memory.py) with
semantic similarity search (embedding_store.py) to return the
most relevant past episodes for any incoming query.

Main function Person 2 calls: recall_relevant_episodes()
Startup function Person 2 calls once on boot: startup_load()
"""

import sqlite3
import json
from episodic_memory import read_recent_episodes
from embedding_store import search_similar_episodes, load_existing_embeddings_from_db


# ---------------------------------------------------------------------------
# 1. Helper — fetch full episode rows by ids
# ---------------------------------------------------------------------------

def fetch_episodes_by_ids(
    episode_ids: list,
    db_path: str = "episodic_memory.db",
) -> list:
    if not episode_ids:
        return []

    placeholders = ",".join("?" * len(episode_ids))
    select_sql = f"""
    SELECT id, session_id, timestamp, query_text, intent_classified,
           sql_generated, result_summary, entities_involved,
           findings_text, chart_generated
    FROM   episodic_memory
    WHERE  id IN ({placeholders})
    ORDER BY timestamp DESC
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(select_sql, episode_ids).fetchall()

    episodes = []
    for row in rows:
        episode = dict(row)
        episode["entities_involved"] = json.loads(episode["entities_involved"] or "{}")
        episode["chart_generated"] = bool(episode["chart_generated"])
        episodes.append(episode)

    return episodes


# ---------------------------------------------------------------------------
# 2. Main recall function
# ---------------------------------------------------------------------------

def recall_relevant_episodes(
    query_text: str,
    session_id: str = None,
    top_k: int = 5,
    db_path: str = "episodic_memory.db",
) -> list:
    """
    Returns the most relevant past episodes for a given query.
    Combines semantic similarity search with recent session history.

    Args:
        query_text: Incoming natural-language query.
        session_id: Current session id — if provided, recent session
                    episodes are merged in for continuity.
        top_k:      Number of episodes to return.
        db_path:    Path to the SQLite database file.

    Returns:
        List of episode dicts sorted by timestamp DESC, deduplicated.
    """
    # Step 1: semantic search — fetch double to allow filtering
    candidate_ids = search_similar_episodes(query_text, top_k=top_k * 2)

    # Step 2: fetch full episode objects for candidates
    semantic_episodes = fetch_episodes_by_ids(candidate_ids, db_path=db_path)

    # Step 3: merge with recent session episodes if session_id provided
    if session_id:
        recent = read_recent_episodes(session_id, limit=3, db_path=db_path)
        # Merge and deduplicate by id
        seen_ids = {ep["id"] for ep in semantic_episodes}
        for ep in recent:
            if ep["id"] not in seen_ids:
                semantic_episodes.append(ep)
                seen_ids.add(ep["id"])

    # Step 4: sort by timestamp DESC
    semantic_episodes.sort(key=lambda x: x["timestamp"], reverse=True)

    # Step 5: return top_k
    return semantic_episodes[:top_k]


# ---------------------------------------------------------------------------
# 3. Format episodes for LLM prompt injection
# ---------------------------------------------------------------------------

def format_episodes_for_prompt(episodes: list) -> str:
    """
    Formats a list of episode dicts into a clean string block
    ready to be injected into an LLM system prompt.

    Args:
        episodes: List of episode dicts from recall_relevant_episodes.

    Returns:
        Formatted string block.
    """
    if not episodes:
        return "No relevant past episodes found."

    lines = []
    for ep in episodes:
        entities = ep.get("entities_involved", {})
        states = entities.get("states", [])
        orgs = entities.get("orgs", [])
        block = (
            f"[Episode {ep['id']} | {ep['timestamp']} | Intent: {ep['intent_classified']}]\n"
            f"Query: {ep['query_text']}\n"
            f"Findings: {ep['findings_text']}\n"
            f"Entities: states={states}, orgs={orgs}\n"
            f"---"
        )
        lines.append(block)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Startup load
# ---------------------------------------------------------------------------

def startup_load(db_path: str = "episodic_memory.db") -> None:
    """
    Call this once when the app boots.
    Rebuilds the in-memory vector store from persisted SQLite episodes.
    """
    load_existing_embeddings_from_db(db_path=db_path)
    print("[episodic_recall] Episodic memory ready.")


# ---------------------------------------------------------------------------
# 5. __main__ test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from episodic_memory import init_episodic_db, write_episode
    from embedding_store import add_episode_embedding, vector_store

    DB_PATH = "episodic_recall_test.db"

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print("=" * 62)
    print("RosterIQ - Episodic Recall Self-Test")
    print("=" * 62)

    init_episodic_db(db_path=DB_PATH)

    # Write 4 sample episodes
    samples = [
        {
            "query_text": "Show me stuck ROs in Kansas Medicaid FFS",
            "intent_classified": "data_query",
            "sql_generated": "SELECT * FROM ros WHERE IS_STUCK=1 AND CNT_STATE='KS'",
            "result_summary": "3 ROs stuck in DART_GENERATION in KS.",
            "entities_involved_dict": {"states": ["KS"], "orgs": ["MercyOne"], "ros": ["RO-101"], "markets": []},
            "findings_text": "3 ROs stuck in DART_GENERATION in Kansas. MercyOne is the primary contributor with 41% rejection rate.",
            "chart_generated": True,
        },
        {
            "query_text": "Why is the Florida market below threshold?",
            "intent_classified": "market_health_report",
            "sql_generated": "SELECT * FROM markets WHERE MARKET='FL' AND below_threshold=1",
            "result_summary": "FL at 71% success, 4 active ROs with avg rejection 38%.",
            "entities_involved_dict": {"states": ["FL"], "orgs": ["FL Health Group"], "ros": [], "markets": ["Florida"]},
            "findings_text": "Florida market dropped to 71% success rate. Primary driver is REJ_REC_CNT not FAIL_REC_CNT — source data compliance issue.",
            "chart_generated": True,
        },
        {
            "query_text": "Which orgs have the highest rejection rates this month?",
            "intent_classified": "record_quality_audit",
            "sql_generated": "SELECT ORG_NM, AVG(rejection_rate) FROM ros GROUP BY ORG_NM ORDER BY AVG(rejection_rate) DESC",
            "result_summary": "Top rejectors: MercyOne 41%, FL Health Group 38%, TX Partners 29%.",
            "entities_involved_dict": {"states": ["KS", "FL", "TX"], "orgs": ["MercyOne", "FL Health Group", "TX Partners"], "ros": [], "markets": []},
            "findings_text": "MercyOne leads rejections at 41%. All top rejectors are Medicaid FFS — highest compliance burden LOB.",
            "chart_generated": False,
        },
        {
            "query_text": "Are retries improving success rates in Texas?",
            "intent_classified": "retry_effectiveness_analysis",
            "sql_generated": "SELECT RUN_NO, AVG(SCS_PERCENT) FROM markets WHERE MARKET='TX' GROUP BY RUN_NO",
            "result_summary": "TX retry lift: first pass 68%, post-retry 79%.",
            "entities_involved_dict": {"states": ["TX"], "orgs": [], "ros": ["RO-202"], "markets": ["Texas"]},
            "findings_text": "Retries in Texas improved success rate by 11 percentage points. Retry strategy is effective for TX market.",
            "chart_generated": False,
        },
    ]

    ep_ids = []
    for s in samples:
        ep_id = write_episode(
            session_id="test-session",
            db_path=DB_PATH,
            **s
        )
        add_episode_embedding(ep_id, s["query_text"], s["findings_text"])
        ep_ids.append(ep_id)

    print(f"\n[test] Written and embedded {len(ep_ids)} episodes: {ep_ids}")

    # Test startup_load (simulate restart)
    print("\n[test] Simulating app restart with startup_load...")
    vector_store["episode_ids"] = []
    vector_store["vectors"] = None
    startup_load(db_path=DB_PATH)

    # Test 1 — semantic search only (no session_id)
    query1 = "Which ROs are stuck in pipeline stages in Kansas?"
    results1 = recall_relevant_episodes(query1, top_k=3, db_path=DB_PATH)
    print(f"\n[test] Query 1: '{query1}'")
    print(f"  Returned {len(results1)} episodes:")
    for ep in results1:
        print(f"  >> id={ep['id']} | intent={ep['intent_classified']} | query={ep['query_text'][:60]}")
    assert results1[0]["id"] == ep_ids[0], "Expected KS stuck RO episode to rank first"
    print("  [PASS] Correct episode ranked first.")

    # Test 2 — with session_id (recent episodes merged in)
    query2 = "What is driving Florida market failures?"
    results2 = recall_relevant_episodes(query2, session_id="test-session", top_k=4, db_path=DB_PATH)
    print(f"\n[test] Query 2 (with session_id): '{query2}'")
    print(f"  Returned {len(results2)} episodes:")
    for ep in results2:
        print(f"  >> id={ep['id']} | intent={ep['intent_classified']} | query={ep['query_text'][:60]}")

    # Test 3 — format for prompt
    print("\n[test] Formatted prompt output:")
    print(format_episodes_for_prompt(results1))

    # Test 4 — empty case
    empty_output = format_episodes_for_prompt([])
    assert empty_output == "No relevant past episodes found."
    print("\n[PASS] Empty case handled correctly.")

    os.remove(DB_PATH)
    print("\n[OK] All episodic recall tests passed.")
    print("=" * 62)