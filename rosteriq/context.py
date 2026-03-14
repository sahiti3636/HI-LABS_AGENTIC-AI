"""
RosterIQ Context & Global Variables
Manages the domain-specific context and global pipeline state.
"""

import time
import logging
from typing import Any
from rosteriq.data.loader import get_connection, get_schema
from rosteriq.session import get_or_create_session

logger = logging.getLogger(__name__)

# Cache for global variables
_global_vars_cache: dict[str, Any] = {}
_last_computed_time: float = 0
CACHE_TTL = 300  # 5 minutes


def get_global_vars(force_refresh: bool = False) -> dict[str, Any]:
    """
    Compute and return global pipeline metrics.
    Uses an in-memory cache with dirty-flag/TTL mechanism.
    """
    global _global_vars_cache, _last_computed_time
    
    now = time.time()
    if not force_refresh and (now - _last_computed_time < CACHE_TTL) and _global_vars_cache:
        return _global_vars_cache

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Basic counts from roster_enriched
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT ORG_NM), COUNT(DISTINCT CNT_STATE) FROM roster_enriched")
        tot, orgs, states = cursor.fetchone()

        # 2. Status counts
        cursor.execute("SELECT COUNT(*) FROM roster_enriched WHERE DART_REVIEW_HEALTH = 'Green' AND SPS_LOAD_HEALTH = 'Green'")
        success = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM roster_enriched WHERE LATEST_STAGE_NM = 'FAILED'")
        failed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM stuck_base")
        stuck = cursor.fetchone()[0]

        # 3. Average success percentage
        cursor.execute("SELECT AVG(SCS_PCT_FILE) FROM audit_base WHERE SCS_PCT_FILE IS NOT NULL")
        avg_scs = cursor.fetchone()[0] or 0

        _global_vars_cache = {
            'total_files': tot,
            'success_files': success,
            'failed_files': failed,
            'stuck_files': stuck,
            'avg_scs_pct': round(float(avg_scs), 2),
            'unique_orgs': orgs,
            'unique_states': states,
            'success_rate': round((success / tot * 100), 2) if tot > 0 else 0,
            'failure_rate': round((failed / tot * 100), 2) if tot > 0 else 0,
        }
        _last_computed_time = now
        return _global_vars_cache

    except Exception as e:
        logger.error(f"Error computing global vars: {e}")
        return _global_vars_cache or {}


def build_context_package(query: str, session_id: str) -> dict[str, Any]:
    """
    Assemble the complete context package for the LLM.
    Includes: schema, global_state, episodic_history (last 3), and FAISS stubs.
    """
    session = get_or_create_session(session_id)
    
    # 1. Episodic History (last 3 interactions)
    # Filter only user/assistant pairs
    history = session.history
    turns = []
    # Identify turns by looking for user role
    for i in range(len(history) - 1, -1, -1):
        if history[i]['role'] == 'user':
            turns.append(history[i])
            if len(turns) >= 3:
                break
    
    # 2. FAISS Search Stubs (Simulated)
    # In a real system, we would embed 'query' and search the vector store
    relevant_rows = f"FAISS: Found 5 rows from roster_enriched matching '{query[:20]}'"
    domain_chunks = "DOMAIN: Found relevant processing logic for SCS_PCT calculation."

    context_package = {
        "schema": get_schema(),
        "global_state": get_global_vars(),
        "episodic_history": turns[::-1], # chronological order
        "relevant_rows": relevant_rows,
        "domain_chunks": domain_chunks,
        "session_meta": session.get_context()
    }
    
    return context_package
