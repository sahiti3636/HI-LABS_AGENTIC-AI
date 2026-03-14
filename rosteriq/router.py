"""
RosterIQ Router
Intent classification (Gemini few-shot) + complexity routing for data queries.
"""

import re
import json
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')

# ──────────────────────────────────────────────────────────────
# Intent Definitions
# ──────────────────────────────────────────────────────────────
INTENTS = [
    'data_query',
    'run_procedure',
    'global_stat',
    'memory_recall',
    'web_search',
    'procedure_update',
    'multi_step',
    'visualization',
]

# Human-readable hypothesis templates for zero-shot classification
INTENT_HYPOTHESES = {
    'data_query':        'This is a question about data, records, files, or database queries.',
    'run_procedure':     'This is a request to run a workflow, procedure, or pipeline process.',
    'global_stat':       'This is a request for an overview, summary statistic, or dashboard metric.',
    'memory_recall':     'This is a request to recall previous conversation context or memory.',
    'web_search':        'This is a request to search the web or find external information.',
    'procedure_update':  'This is a request to update, modify, or create a procedure or rule.',
    'multi_step':        'This requires multiple sequential steps or a complex multi-part analysis.',
    'visualization':     'This is a request to create a chart, graph, plot, or visual dashboard.',
}

CONFIDENCE_THRESHOLD = 0.55

# ──────────────────────────────────────────────────────────────
# Complexity Keywords
# ──────────────────────────────────────────────────────────────
COMPLEX_KEYWORDS = [
    'join', 'compare', 'trend', 'correlat', 'across',
    'versus', 'vs', 'relationship', 'over time',
    'month over month', 'combine', 'cross-table',
    'anomal', 'outlier', 'regress', 'predict',
    'multi', 'between.*and', 'aggregate across',
]

SIMPLE_KEYWORDS = [
    'how many', 'count', 'list', 'show', 'filter',
    'which', 'what is', 'total', 'top', 'bottom',
    'average', 'mean', 'stuck', 'failed',
]

# ──────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    intent: str
    confidence: float
    was_ambiguous: bool = False


@dataclass
class RoutingDecision:
    intent: str
    confidence: float
    complexity: str          # 'simple' | 'complex' | 'n/a'
    route_to: str            # 'sqlcoder' | 'llm_api' | 'handler' | 'fallback'
    was_ambiguous: bool = False


# ──────────────────────────────────────────────────────────────
# Gemini Intent Classifier
# ──────────────────────────────────────────────────────────────
_GEMINI_INTENT_PROMPT = """
You are the central intent router for RosterIQ, a database query and analytics platform.
Your job is to read the user's input and classify it into ONE of the specific intent categories listed below.

CRITICAL RULES:
1. You must output ONLY the exact name of the intent in JSON format: {{"intent": "<intent_name>"}}
2. Do not include any explanations or conversational text.

INTENT DEFINITIONS:
- "global_stat": Use this ONLY for simple, high-level aggregate metrics. Total counts, averages, min/max where the expected output is a single number or very simple summary.
- "data_query": Use this for complex data retrieval. Filtering records, listing specific rows, returning multiple columns of information.
- "run_procedure": Use this when the user wants to run a named workflow, pipeline step, or predefined procedure.
- "visualization": Use this when the user wants a chart, graph, plot, or visual dashboard.
- "multi_step": Use this when the request requires multiple sequential analysis steps or complex multi-part reasoning.
- "memory_recall": Use this when the user asks to recall or reference a previous conversation or query.
- "web_search": Use this if the user asks for external information not in the database.
- "procedure_update": Use this if the user wants to update, modify, or create a procedure or rule.
- "unsupported": Use this if the query is nonsensical or completely unrelated to RosterIQ.

FEW-SHOT EXAMPLES:
User: "What is the total number of files processed?"
{{"intent": "global_stat"}}

User: "Show me the names of the files processed yesterday that failed validation."
{{"intent": "data_query"}}

User: "How many organizations are in the system?"
{{"intent": "global_stat"}}

User: "List all stuck files from New York."
{{"intent": "data_query"}}

User: "What is the average success rate across all states?"
{{"intent": "global_stat"}}

User: "Give me a breakdown of processing times by organization for last month."
{{"intent": "data_query"}}

User: "Run the state audit procedure for California."
{{"intent": "run_procedure"}}

User: "Show me a chart of monthly success rates."
{{"intent": "visualization"}}

User: "Search the web for the latest compliance regulations."
{{"intent": "web_search"}}

Now classify this query:
User: "{query}"
"""

_gemini_model = None


def _get_gemini_model():
    """Lazy-load Gemini model on first use."""
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai
        from rosteriq.config import GOOGLE_API_KEY
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY not set in .env")
        genai.configure(api_key=GOOGLE_API_KEY)
        _gemini_model = genai.GenerativeModel('gemini-flash-latest')
        logger.info('Gemini router loaded.')
    return _gemini_model


# ──────────────────────────────────────────────────────────────
# BART Classifier (used only for complexity, not intent)
# ──────────────────────────────────────────────────────────────
_classifier = None


def _get_classifier():
    """Lazy-load the BART-MNLI pipeline (for complexity classification only)."""
    global _classifier
    if _classifier is None:
        logger.info('Loading facebook/bart-large-mnli (complexity classifier) ...')
        from transformers import pipeline
        _classifier = pipeline(
            'zero-shot-classification',
            model='facebook/bart-large-mnli',
            device=-1,
        )
        logger.info('BART-MNLI loaded.')
    return _classifier


# ──────────────────────────────────────────────────────────────
# Intent Classification (Gemini Few-Shot)
# ──────────────────────────────────────────────────────────────
def classify_intent(query: str) -> ClassificationResult:
    """
    Classify a user query into one of 8 intents using Gemini few-shot prompting.
    Falls back to 'data_query' if Gemini is unavailable or returns an unexpected value.
    """
    valid_intents = set(INTENTS + ['unsupported'])

    try:
        model = _get_gemini_model()
        prompt = _GEMINI_INTENT_PROMPT.format(query=query)
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Strip markdown code fences if present
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        parsed = json.loads(text)
        intent = parsed.get('intent', 'data_query')

        if intent not in valid_intents:
            logger.warning(f'Gemini returned unknown intent "{intent}", defaulting to data_query.')
            intent = 'data_query'

        if intent == 'unsupported':
            intent = 'data_query'  # degrade gracefully

        logger.info(f'Gemini classified: "{query[:60]}" → {intent}')
        return ClassificationResult(intent=intent, confidence=1.0, was_ambiguous=False)

    except Exception as e:
        logger.warning(f'Gemini classification failed: {e}. Defaulting to data_query.')
        return ClassificationResult(intent='data_query', confidence=0.0, was_ambiguous=True)


# ──────────────────────────────────────────────────────────────
# Complexity Classification (for data_query)
# ──────────────────────────────────────────────────────────────
def classify_complexity(query: str) -> str:
    """
    Classify a data query as 'simple' or 'complex'.
    Strategy: rule-based keyword check first, BART fallback if inconclusive.
    """
    q_lower = query.lower()

    # Rule-based check
    complex_score = sum(
        1 for kw in COMPLEX_KEYWORDS
        if re.search(kw, q_lower)
    )
    simple_score = sum(
        1 for kw in SIMPLE_KEYWORDS
        if re.search(kw, q_lower)
    )

    if complex_score >= 2:
        return 'complex'
    if simple_score >= 2 and complex_score == 0:
        return 'simple'

    # Inconclusive → use BART as tiebreaker
    classifier = _get_classifier()
    result = classifier(
        query,
        [
            'This is a simple single-table database query with basic filtering.',
            'This is a complex multi-table query requiring joins, comparisons, or derived calculations.',
        ],
        multi_label=False,
    )
    top_label = result['labels'][0]
    if 'simple' in top_label.lower():
        return 'simple'
    return 'complex'


# ──────────────────────────────────────────────────────────────
# Full Routing Pipeline
# ──────────────────────────────────────────────────────────────
def route(query: str) -> RoutingDecision:
    """
    Full routing pipeline:
      1. Classify intent (BART-MNLI)
      2. If data_query → classify complexity → route to sqlcoder or llm_api
      3. Otherwise → route to handler
    """
    classification = classify_intent(query)

    if classification.intent == 'data_query':
        complexity = classify_complexity(query)
        route_to = 'sqlcoder' if complexity == 'simple' else 'llm_api'
    elif classification.intent in ('multi_step', 'visualization'):
        complexity = 'complex'
        route_to = 'llm_api'
    else:
        complexity = 'n/a'
        route_to = 'handler'

    decision = RoutingDecision(
        intent=classification.intent,
        confidence=classification.confidence,
        complexity=complexity,
        route_to=route_to,
        was_ambiguous=classification.was_ambiguous,
    )
    logger.info(
        f'Route: "{query[:50]}..." → intent={decision.intent} '
        f'complexity={decision.complexity} route={decision.route_to} '
        f'conf={decision.confidence}'
    )
    return decision


# ──────────────────────────────────────────────────────────────
# SQLCoder → LLM Fallback Chain
# ──────────────────────────────────────────────────────────────
def execute_with_fallback(
    query: str,
    sqlcoder_fn,
    llm_fn,
    validate_fn=None,
) -> dict:
    """
    Execute a data query with automatic fallback:
      1. Try sqlcoder_fn(query)
      2. If validate_fn fails → re-route to llm_fn(query)

    Args:
        query:        The user's natural language query.
        sqlcoder_fn:  Callable that returns SQL string from local SQLCoder.
        llm_fn:       Callable that returns SQL string from LLM API.
        validate_fn:  Optional callable(sql) → bool. Default: syntax check.

    Returns:
        dict with keys: sql, source ('sqlcoder'|'llm_api'), fallback_used
    """
    if validate_fn is None:
        validate_fn = _basic_sql_validate

    # Attempt 1: SQLCoder
    try:
        sql = sqlcoder_fn(query)
        if sql and validate_fn(sql):
            return {'sql': sql, 'source': 'sqlcoder', 'fallback_used': False}
        logger.warning(f'SQLCoder output failed validation, falling back to LLM.')
    except Exception as e:
        logger.warning(f'SQLCoder error: {e}. Falling back to LLM.')

    # Attempt 2: LLM API
    try:
        sql = llm_fn(query)
        return {'sql': sql, 'source': 'llm_api', 'fallback_used': True}
    except Exception as e:
        logger.error(f'LLM API also failed: {e}')
        return {'sql': None, 'source': 'error', 'fallback_used': True}


def _basic_sql_validate(sql: str) -> bool:
    """Basic validation: non-empty, starts with SELECT, no obvious errors."""
    if not sql or not sql.strip():
        return False
    s = sql.strip().upper()
    if not s.startswith('SELECT'):
        return False
    # Check balanced parentheses
    if s.count('(') != s.count(')'):
        return False
    return True


# ──────────────────────────────────────────────────────────────
# Intent to Handler Mapping
# ──────────────────────────────────────────────────────────────
from rosteriq import handlers

INTENT_HANDLER_MAP = {
    'data_query':       handlers.handle_data_query,
    'run_procedure':    handlers.handle_run_procedure,
    'global_stat':      handlers.handle_global_stat,
    'memory_recall':    handlers.handle_memory_recall,
    'web_search':       handlers.handle_web_search,
    'procedure_update': handlers.handle_procedure_update,
    'multi_step':       handlers.handle_multi_step,
    'visualization':    handlers.handle_visualization,
}
