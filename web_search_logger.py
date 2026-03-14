"""
web_search_logger.py
====================
RosterIQ — AI agent that diagnoses healthcare provider roster pipeline failures.

Connects web search output to episodic memory so the agent can recall
past web searches in future sessions.

Depends on (pre-existing modules — do NOT recreate):
    episodic_memory.py   — write_episode, read_recent_episodes
    embedding_store.py   — add_episode_embedding
    web_search.py        — run_web_search

Usage:
    result = run_web_search(trigger, params)
    log    = log_web_search_to_memory(result, session_id)
    past   = recall_web_searches(session_id)
    prompt = format_recalled_searches_for_prompt(past)
"""

import os
import json
import datetime

from episodic_memory import write_episode, read_recent_episodes
from embedding_store import add_episode_embedding


# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH: str = "episodic_memory.db"


# ---------------------------------------------------------------------------
# 2. Private helper — _format_results_as_findings
# ---------------------------------------------------------------------------

def _format_results_as_findings(search_result: dict) -> str:
    """
    Format the result dict returned by any of the 3 web search functions
    into a clean findings string ready for episodic memory storage.

    Parameters
    ----------
    search_result : dict
        Result dict from run_web_search / search_regulatory_changes /
        search_failure_status / search_org_context.

    Returns
    -------
    str
        Multi-line findings string, or a 'no results' message.
    """
    trigger      = search_result.get("trigger", "unknown")
    query        = search_result.get("query", "")
    results      = search_result.get("results", [])
    result_count = search_result.get("result_count", len(results))

    if not results:
        return f"Web search returned no results for query: {query}"

    lines = [
        f"Web search triggered by: {trigger}",
        f"Search query: {query}",
        f"Results found: {result_count}",
        "",
    ]

    for idx, item in enumerate(results, start=1):
        title   = item.get("title", "")
        content = item.get("content", "")
        url     = item.get("url", "")
        lines.append(f"Result {idx}: {title}")
        lines.append(content)
        lines.append(f"Source: {url}")
        lines.append("")

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# 3. Private helper — _extract_entities
# ---------------------------------------------------------------------------

def _extract_entities(search_result: dict) -> dict:
    """
    Extract key entities from the search result dict for indexing in
    episodic memory.

    Parameters
    ----------
    search_result : dict
        Result dict from any web search function.

    Returns
    -------
    dict
        Flat entity dict with 6 string-valued keys.
    """
    return {
        "trigger":        search_result.get("trigger", ""),
        "state":          search_result.get("state", ""),
        "org_nm":         search_result.get("org_nm", ""),
        "failure_status": search_result.get("failure_status", ""),
        "lob":            search_result.get("lob", ""),
        "result_count":   str(search_result.get("result_count", 0)),
    }


# ---------------------------------------------------------------------------
# 4. Primary logging function — log_web_search_to_memory
# ---------------------------------------------------------------------------

def log_web_search_to_memory(
    search_result: dict,
    session_id: str,
    db_path: str = DEFAULT_DB_PATH,
) -> dict:
    """
    Log a web search result to episodic memory and build a semantic embedding.

    Parameters
    ----------
    search_result : dict
        Result dict returned by run_web_search (or any of the 3 search
        functions directly).
    session_id : str
        Unique identifier for the current agent session.
    db_path : str
        Path to the SQLite database file (default: episodic_memory.db).

    Returns
    -------
    dict
        Logging receipt with keys: episode_id, session_id, trigger,
        query_text, findings_preview, logged_at, success, error.
    """
    try:
        # ── Step 1: Build findings text ───────────────────────────────────
        findings_text = _format_results_as_findings(search_result)

        # ── Step 2: Extract entities ──────────────────────────────────────
        entities = _extract_entities(search_result)

        # ── Step 3: Build natural-language query_text per trigger ─────────
        trigger       = search_result.get("trigger", "")
        state         = search_result.get("state", "")
        lob           = search_result.get("lob", "")
        org_nm        = search_result.get("org_nm", "")
        failure_status = search_result.get("failure_status", "")
        rejection_rate = search_result.get("rejection_rate", 0.0)
        result_count  = search_result.get("result_count", 0)

        if trigger == "high_rejection_rate":
            query_text = (
                f"Web search: regulatory changes for {state} {lob} "
                f"rejection rate {rejection_rate:.0%}"
            )
        elif trigger == "unknown_failure_status":
            query_text = (
                f"Web search: failure status {failure_status} meaning for {org_nm}"
            )
        elif trigger == "unknown_org_anomaly":
            query_text = (
                f"Web search: organization context for {org_nm} in {state}"
            )
        else:
            query_text = f"Web search: {search_result.get('query', '')}"

        # ── Step 4: Write episode to SQLite ───────────────────────────────
        episode_id = write_episode(
            session_id=session_id,
            query_text=query_text,
            intent_classified="web_search",
            sql_generated="",
            result_summary=(
                f"Web search returned {result_count} results for trigger: {trigger}"
            ),
            entities_involved_dict=entities,
            findings_text=findings_text,
            chart_generated=False,
            db_path=db_path,
        )

        # ── Step 5: Add semantic embedding ────────────────────────────────
        add_episode_embedding(episode_id, query_text, findings_text)

        # ── Step 6: Return success receipt ────────────────────────────────
        return {
            "episode_id":       episode_id,
            "session_id":       session_id,
            "trigger":          trigger,
            "query_text":       query_text,
            "findings_preview": findings_text[:200],
            "logged_at":        datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "success":          True,
            "error":            None,
        }

    except Exception as exc:  # noqa: BLE001
        return {
            "episode_id":       None,
            "session_id":       session_id,
            "trigger":          search_result.get("trigger", "unknown"),
            "query_text":       "",
            "findings_preview": "",
            "logged_at":        datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "success":          False,
            "error":            str(exc),
        }


# ---------------------------------------------------------------------------
# 5. Recall function — recall_web_searches
# ---------------------------------------------------------------------------

def recall_web_searches(
    session_id: str,
    limit: int = 5,
    db_path: str = DEFAULT_DB_PATH,
) -> list:
    """
    Retrieve recent web-search episodes for a session from episodic memory.

    Fetches (limit * 3) episodes to account for interspersed non-web-search
    episodes, then filters to only those with intent_classified='web_search',
    and returns at most *limit* results.

    Parameters
    ----------
    session_id : str
        Session to retrieve episodes for.
    limit : int
        Maximum number of web-search episodes to return (default 5).
    db_path : str
        Path to the SQLite database file (default: episodic_memory.db).

    Returns
    -------
    list
        List of episode dicts (all columns), filtered to web_search intent.
    """
    all_episodes = read_recent_episodes(session_id, limit * 3, db_path)
    web_episodes = [
        ep for ep in all_episodes
        if ep.get("intent_classified") == "web_search"
    ]
    return web_episodes[:limit]


# ---------------------------------------------------------------------------
# 6. Prompt formatter — format_recalled_searches_for_prompt
# ---------------------------------------------------------------------------

def format_recalled_searches_for_prompt(episodes: list) -> str:
    """
    Format a list of recalled web-search episodes into a string ready for
    injection into an LLM prompt.

    Parameters
    ----------
    episodes : list
        List of episode dicts from recall_web_searches.

    Returns
    -------
    str
        Formatted multi-line string, or a 'no results' line if empty.
    """
    if not episodes:
        return "---\nNo previous web searches found."

    lines = [f"Previous Web Searches ({len(episodes)} found):", ""]

    for ep in episodes:
        timestamp      = ep.get("timestamp", "")
        intent         = ep.get("intent_classified", "")
        query_text     = ep.get("query_text", "")
        findings_text  = ep.get("findings_text", "")

        # Entities dict holds the trigger stored at write time
        entities = ep.get("entities_involved", {})
        trigger_label  = entities.get("trigger", intent)

        lines.append(f"[{timestamp}] {trigger_label} — {query_text}")
        lines.append(f"Findings: {findings_text[:200]}")
        lines.append("")

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# 7. __main__ test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from web_search import run_web_search
    from episodic_memory import init_episodic_db

    TEST_SESSION_ID = "test_session_ws_001"

    TEST_CASES = [
        {
            "trigger": "high_rejection_rate",
            "params": {
                "state": "KS",
                "rejection_rate": 0.42,
                "lob": "Medicaid FFS",
            },
        },
        {
            "trigger": "unknown_failure_status",
            "params": {
                "failure_status": "DART_SCHEMA_MISMATCH",
                "org_nm": "Sunflower Health Plan",
            },
        },
        {
            "trigger": "unknown_org_anomaly",
            "params": {
                "org_nm": "Centene Corporation",
                "state": "KS",
                "anomaly_type": "high_rejection_rate",
            },
        },
    ]

    # Ensure the DB table exists before writing
    init_episodic_db(db_path=DEFAULT_DB_PATH)

    print("\n" + "=" * 70)
    print("  RosterIQ — Web Search Logger Test Suite")
    print("=" * 70 + "\n")

    # ── Step A: Run each trigger, log to memory, and print receipt ────────
    for i, case in enumerate(TEST_CASES, start=1):
        trigger = case["trigger"]
        params  = case["params"]

        # 1. Execute the web search
        result = run_web_search(trigger, params)

        # 2. Log to episodic memory
        log = log_web_search_to_memory(result, TEST_SESSION_ID)

        episode_id       = log["episode_id"]
        query_text       = log["query_text"]
        findings_preview = log["findings_preview"]
        success          = log["success"]
        error            = log["error"]

        # 3. Print receipt
        print(f"[{i}] Trigger     : {trigger}")
        print(f"     Episode ID  : {episode_id}")
        print(f"     Query text  : {query_text}")
        print(f"     Preview     : {findings_preview[:150]}...")
        print(f"     Success     : {success}")
        print(f"     Error       : {error}")
        print()

    # ── Step B: Recall and display past web-search episodes ───────────────
    print("=" * 70)
    print("  Recalling web search episodes from episodic memory")
    print("=" * 70 + "\n")

    recalled = recall_web_searches(TEST_SESSION_ID)
    print(f"Total episodes recalled: {len(recalled)}\n")

    prompt_block = format_recalled_searches_for_prompt(recalled)
    print(prompt_block)
    print("\n" + "=" * 70)
