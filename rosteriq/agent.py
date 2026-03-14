"""
RosterIQ Agent
Main entrypoint — implements the full agent loop (Sense-Think-Act).
"""

import logging
import time
import uuid
import concurrent.futures
import google.generativeai as genai
from typing import Any, Optional

from rosteriq.data.loader import get_connection, get_schema
from rosteriq.context import get_global_vars, build_context_package
from rosteriq.router import route, INTENT_HANDLER_MAP, execute_with_fallback
from rosteriq.session import get_or_create_session
from rosteriq.config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# Timeout for handler execution + LLM interpretation
EXEC_TIMEOUT = 15.0


def init():
    """Initialize the agent: load data into SQLite, compute global vars."""
    print('[agent] Initializing RosterIQ ...')
    conn = get_connection()       # triggers CSV → SQLite load
    gv = get_global_vars(force_refresh=True)
    schema = get_schema()
    print(f'[agent] Tables loaded: {list(schema.keys())}')
    print('[agent] Ready.')
    return conn


def _llm_nl_interpretation(query: str, raw_result: Any, context: dict) -> str:
    """
    Use Gemini to interpret raw data results into a natural language response.
    """
    if not GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY not set. Using mock interpretation.")
        return _mock_interpretation_fallback(query, raw_result)

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    User Query: {query}
    Raw Data Result: {raw_result}
    Context: {context.get('global_state')}
    
    Provide a concise, professional summary of these results for the RosterIQ business user. 
    Explain what the numbers mean for pipeline health.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini Interpretation Error: {e}")
        return _mock_interpretation_fallback(query, raw_result)


def _llm_sql_generation(query: str, context: dict) -> str:
    """
    Use Gemini to generate SQL from natural language.
    """
    if not GOOGLE_API_KEY:
        return "SELECT * FROM roster_enriched LIMIT 5" # Default fallback
    
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    schema_str = str(context.get('schema'))
    
    prompt = f"""
    SQLite Schema: {schema_str}
    User Query: {query}
    
    Generate a valid SQLite query to answer the user request. 
    Return ONLY the SQL string. No markdown, no explanation.
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean up any potential markdown
        sql = response.text.strip()
        if '```sql' in sql:
            sql = sql.split('```sql')[1].split('```')[0].strip()
        elif '```' in sql:
            sql = sql.split('```')[1].split('```')[0].strip()
        return sql
    except Exception as e:
        logger.error(f"Gemini SQL Gen Error: {e}")
        return "SELECT * FROM roster_enriched LIMIT 5"


def _mock_interpretation_fallback(query: str, raw_result: Any) -> str:
    """Fallback interpretation if LLM is unavailable."""
    if not raw_result:
        return f"I couldn't find any data for your query about '{query}'."
    if isinstance(raw_result, list):
        return f"I found {len(raw_result)} relevant records. Top results include {raw_result[0].get('ORG_NM', 'various orgs')}."
    return str(raw_result)


def _dummy_sqlcoder(query: str) -> str:
    """Mock SQLCoder: returns simple SELECTs for keyword matches."""
    q = query.lower()
    if 'stuck' in q: return "SELECT * FROM stuck_base"
    if 'audit' in q or 'quality' in q: return "SELECT * FROM audit_base"
    if 'retry' in q: return "SELECT * FROM retry_base"
    if 'market' in q or 'trend' in q: return "SELECT * FROM market_base"
    return "SELECT * FROM roster_enriched LIMIT 10"


def _dummy_llm_api(query: str) -> str:
    """Mock LLM API for SQL generation."""
    return "SELECT CNT_STATE, COUNT(*) as cnt FROM roster_enriched GROUP BY CNT_STATE ORDER BY cnt DESC"


def run_agent(query_text: str, session_id: Optional[str] = None) -> dict:
    """
    The main agent loop: 
    Accept query -> Build context -> Classify intent -> Route -> Execute -> Interpret -> Log.
    """
    start_time = time.time()
    session = get_or_create_session(session_id)
    session.increment_query()
    
    # 1. Build Context Package
    context_pkg = build_context_package(query_text, session.session_id)
    
    # 2. Route & Execute (with Timeout)
    try:
        decision = route(query_text)
        handler = INTENT_HANDLER_MAP.get(decision.intent)
        
        if not handler:
            raise ValueError(f"Unknown intent: {decision.intent}")

        # Prepare handler parameters
        params = {"query_text": query_text}
        if decision.intent == 'data_query':
            params['sql_fn'] = lambda q: execute_with_fallback(q, _dummy_sqlcoder, lambda q: _llm_sql_generation(q, context_pkg))
            params['context_pkg'] = context_pkg
        elif decision.intent == 'run_procedure':
            params = {"procedure_name": "generate_state_audit", "params": {"state": "CA"}} # Default
        elif decision.intent == 'global_stat':
            params = {"stat_key": None}
        elif decision.intent == 'multi_step':
            params['context_pkg'] = context_pkg

        # Execute handler with timeout
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(handler, **params)
            try:
                handler_response = future.result(timeout=EXEC_TIMEOUT)
            except concurrent.futures.TimeoutError:
                logger.warning(f"Handler {decision.intent} timed out.")
                handler_response = {
                    "result": "Timeout",
                    "reasoning": "Processing took too long (>15s).",
                    "sources": ["system-timeout"],
                    "chart_hint": None
                }

        # 3. NL Interpretation
        nl_response = _llm_nl_interpretation(query_text, handler_response['result'], context_pkg)
        
        final_response = {
            "query": query_text,
            "intent": decision.intent,
            "answer": nl_response,
            "data": handler_response['result'],
            "reasoning": handler_response['reasoning'],
            "sources": handler_response['sources'],
            "chart_hint": handler_response['chart_hint'],
            "session_id": session.session_id,
            "exec_time_sec": round(time.time() - start_time, 3)
        }

        # 4. Log to episodic memory (last 10 queries track)
        session.add_message('user', query_text)
        session.add_message('assistant', nl_response, intent=decision.intent)
        
        return final_response

    except Exception as e:
        logger.error(f"Agent Loop Error: {e}")
        return {
            "query": query_text,
            "answer": "I encountered an internal error while processing your request.",
            "error": str(e),
            "exec_time_sec": round(time.time() - start_time, 3)
        }


def get_session_history(session_id: str) -> list:
    """Return the history of a specific session."""
    session = get_or_create_session(session_id)
    return session.history


if __name__ == '__main__':
    init()
    # Test turn 1
    sid = "test-session-123"
    print("\n--- TURN 1 ---")
    res1 = run_agent("Show me stuck files in CA", session_id=sid)
    print(f"ANSWER: {res1['answer']}")
    
    # Test turn 2
    print("\n--- TURN 2 ---")
    res2 = run_agent("What is the average success rate?", session_id=sid)
    print(f"ANSWER: {res2['answer']}")
    
    # Check history
    print("\n--- HISTORY ---")
    for msg in get_session_history(sid):
        print(f"[{msg['role']}]: {msg['content'][:100]}...")
