"""
RosterIQ Execution Handlers
Standardized intent handlers for the RosterIQ agent.
"""

import os
import json
import logging
import pandas as pd
from typing import Any, Optional
from rosteriq.data.loader import query, query_df, get_schema
from rosteriq.context import get_global_vars
from rosteriq.config import GOOGLE_API_KEY
import google.generativeai as genai

logger = logging.getLogger(__name__)

PROCEDURES_FILE = os.path.join(os.path.dirname(__file__), 'procedures.json')


def _format_response(
    result: Any,
    reasoning: str,
    sources: list[str],
    chart_hint: Optional[str] = None
) -> dict:
    """Standardized response format for all handlers."""
    return {
        "result": result,
        "reasoning": reasoning,
        "sources": sources,
        "chart_hint": chart_hint
    }


def handle_data_query(query_text: str, sql_fn, context_pkg: dict) -> dict:
    """
    Routes a natural language query to a SQL generator and executes it.
    
    Args:
        query_text: The user's query.
        sql_fn: A function that takes (query, context) and returns SQL.
        context_pkg: System/Session context for the model.
    """
    reasoning = "Executing natural language query via SQL fallback chain."
    try:
        # sql_fn is expected to be router.execute_with_fallback or similar
        sql_result = sql_fn(query_text)
        sql = sql_result.get('sql')
        source_model = sql_result.get('source', 'unknown')
        
        if not sql:
            return _format_response(None, "Could not generate valid SQL.", [source_model])

        df = query_df(sql)
        result = df.to_dict(orient='records')
        
        # Add chart hint based on data shape
        chart_hint = None
        if len(df) > 0:
            if 'MONTH' in df.columns or 'CREAT_DT' in df.columns:
                chart_hint = "line_chart"
            elif 'SCS_PCT' in df.columns or 'SCS_PCT_FILE' in df.columns:
                chart_hint = "bar_chart"
            elif len(df.columns) == 2 and df.dtypes.iloc[1] in ['int64', 'float64']:
                chart_hint = "pie_chart"

        return _format_response(
            result,
            f"Generated and executed SQL using {source_model}.",
            [source_model],
            chart_hint
        )
    except Exception as e:
        logger.error(f"Error in handle_data_query: {e}")
        return _format_response(None, f"Execution error: {str(e)}", ["system"])


def handle_run_procedure(procedure_name: str, params: dict) -> dict:
    """
    Loads a procedure from procedures.json, substitutes parameters, and executes.
    """
    if not os.path.exists(PROCEDURES_FILE):
        return _format_response(None, "Procedures file not found.", ["system"])
    
    with open(PROCEDURES_FILE, 'r') as f:
        procedures = json.load(f)
    
    proc = next((p for p in procedures if p['name'] == procedure_name), None)
    if not proc:
        return _format_response(None, f"Procedure '{procedure_name}' not found.", ["procedures.json"])
    
    sql = proc['sql']
    sql_params = []
    
    # Simple positional substitution for consistency with SQLite
    for p_name in proc.get('params', []):
        val = params.get(p_name)
        sql_params.append(val)
        
    try:
        df = query_df(sql, tuple(sql_params))
        return _format_response(
            df.to_dict(orient='records'),
            f"Successfully executed procedure: {proc['description']}",
            ["procedures.json"],
            proc.get('chart_hint')
        )
    except Exception as e:
        return _format_response(None, f"Procedure execution error: {str(e)}", ["procedures.json"])


def handle_global_stat(stat_key: str | None = None) -> dict:
    """
    Retrieves global statistics directly from context.
    """
    gv = get_global_vars()
    if stat_key:
        result = gv.get(stat_key, "Stat not found")
        reasoning = f"Retrieved specific metric: {stat_key}"
    else:
        result = gv
        reasoning = "Retrieved all global pipeline statistics."
        
    return _format_response(result, reasoning, ["in-memory-context"])


def handle_memory_recall(query_text: str, session_id: str = "default") -> dict:
    """
    Recalls episodic memory from previous conversation context.
    (Stub implementation)
    """
    # In a real implementation, this would use an embedding function
    # For now, it returns a placeholder reasoning.
    reasoning = f"Searching episodic memory for: {query_text}"
    result = "Memory recall activated. (Placeholder: No local vector store found, returning recent history summary instead.)"
    return _format_response(result, reasoning, ["session_history"])


def handle_web_search(query_text: str, trigger_reason: str = "External info needed") -> dict:
    """
    Triggers a targeted web search via provider.
    (Stub implementation)
    """
    reasoning = f"Web search triggered because: {trigger_reason}"
    result = f"Search results for: {query_text} (Placeholder: Web search tool not configured.)"
    return _format_response(result, reasoning, ["web_search_provider"])


def handle_procedure_update(procedure_name: str, correction_text: str) -> dict:
    """
    Parses a natural language correction using Gemini and updates procedures.json.
    """
    if not GOOGLE_API_KEY:
        return _format_response(None, "GOOGLE_API_KEY not set for procedure updates.", ["system"])

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
    schema = get_schema()
    
    prompt = f"""
    Context: You are managing a library of SQL procedures for RosterIQ.
    Schema: {schema}
    Target Procedure: {procedure_name}
    Correction/Instruction: {correction_text}
    
    Update or generate the SQLite SQL code for this procedure.
    Return a JSON object with keys: "sql", "description", "params" (list of parameter names).
    Return ONLY the JSON object.
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
            
        new_proc = json.loads(text)
        
        # Load and update procedures.json
        with open(PROCEDURES_FILE, 'r') as f:
            procedures = json.load(f)
            
        # Find and update or append
        updated = False
        for p in procedures:
            if p['name'] == procedure_name:
                p.update(new_proc)
                updated = True
                break
        if not updated:
            new_proc['name'] = procedure_name
            procedures.append(new_proc)
            
        with open(PROCEDURES_FILE, 'w') as f:
            json.dump(procedures, f, indent=4)
            
        return _format_response(
            {"status": "updated", "procedure": procedure_name},
            f"Successfully updated procedure '{procedure_name}' via Gemini parsing.",
            ["gemini", "procedures.json"]
        )
    except Exception as e:
        return _format_response(None, f"Failed to update procedure: {str(e)}", ["gemini"])


def handle_multi_step(query_text: str, context_pkg: dict) -> dict:
    """
    Decomposes a complex query into a sequence of sub-intents using Gemini.
    """
    if not GOOGLE_API_KEY:
        return _format_response(None, "GOOGLE_API_KEY not set for multi-step decomposition.", ["system"])

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    User Query: {query_text}
    Available Intents: data_query, run_procedure, global_stat, visualization
    
    Decompose this complex query into a list of steps. 
    Return a JSON list of objects: {{"intent": "...", "params": {{...}}}}
    Return ONLY the JSON list.
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
            
        steps = json.loads(text)
        
        # In a real system, we'd execute these sequentially. For now, we return the plan.
        return _format_response(
            {"plan": steps},
            f"Decomposed complex query into {len(steps)} sequential steps using Gemini.",
            ["gemini"]
        )
    except Exception as e:
        return _format_response(None, f"Decomposition failed: {str(e)}", ["gemini"])


def handle_visualization(chart_hint: str, data: Any) -> dict:
    """
    Routes data to specific charting metadata.
    """
    reasoning = f"Formatting data for {chart_hint} visualization."
    
    # Map hint to visual metadata
    viz_meta = {
        "type": chart_hint,
        "requires_plotly": True,
        "is_dynamic": True
    }
    
    return _format_response(
        {"data": data, "metadata": viz_meta},
        reasoning,
        ["visualization_engine"],
        chart_hint
    )
