"""
web_search.py
=============
RosterIQ — AI agent that diagnoses healthcare provider roster pipeline failures.
Handles web search for 3 diagnostic triggers via the Tavily API.

Triggers:
  1. rejection_rate > 0.30 AND no Red health flags AND IS_STUCK=0
     → search for regulatory changes explaining the spike
  2. Unknown FAILURE_STATUS string found in the data
     → search for compliance meaning
  3. Unknown ORG_NM appears as an anomaly
     → search for context about that organisation
"""

import datetime
import json
import os
from dotenv import load_dotenv
load_dotenv()
import requests

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------

TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL: str = "https://api.tavily.com/search"
MAX_RESULTS: int = 3          # top results per search
MAX_CONTENT_LENGTH: int = 500  # chars to keep per result content


# ---------------------------------------------------------------------------
# 2. Private Tavily helper
# ---------------------------------------------------------------------------

def _call_tavily(query: str, topic: str = "general") -> list:
    """
    Make a raw POST request to the Tavily search API.

    Parameters
    ----------
    query : str
        Search query string.
    topic : str
        Tavily topic hint ('general', 'news', etc.).

    Returns
    -------
    list
        List of result dicts, each with 'title', 'url', 'content'.
        If Tavily returns a top-level 'answer', it is prepended as a
        special result with url='tavily_answer'.
    """
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": MAX_RESULTS,
        "include_answer": True,
        "topic": topic,
    }

    try:
        response = requests.post(
            TAVILY_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"[WARN] Tavily search failed: {exc}")
        return []

    results: list = []

    # Prepend the direct answer if present
    answer = data.get("answer")
    if answer:
        results.append({
            "title": "Tavily Direct Answer",
            "url": "tavily_answer",
            "content": str(answer)[:MAX_CONTENT_LENGTH],
        })

    # Append individual results, truncating content
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": str(item.get("content", ""))[:MAX_CONTENT_LENGTH],
        })

    return results


# ---------------------------------------------------------------------------
# 3. search_regulatory_changes
# ---------------------------------------------------------------------------

def search_regulatory_changes(
    state: str,
    rejection_rate: float,
    lob: str = "",
) -> dict:
    """
    Search for regulatory changes that might explain a rejection rate spike.
    Triggered when rejection_rate > 0.30 with no structural pipeline issues.

    Parameters
    ----------
    state         : str   — two-letter or full state name
    rejection_rate: float — observed rejection rate (0..1)
    lob           : str   — line of business (optional)

    Returns
    -------
    dict  — search result payload (see module docstring for schema)
    """
    query = (
        f"CMS Medicaid Medicare roster provider data rejection rate spike "
        f"{state} {lob} regulatory changes compliance 2024 2025"
    ).strip()

    error = None
    results = []
    try:
        results = _call_tavily(query, topic="general")
    except Exception as exc:
        error = str(exc)

    return {
        "trigger": "high_rejection_rate",
        "state": state,
        "rejection_rate": rejection_rate,
        "lob": lob,
        "query": query,
        "results": results,
        "result_count": len(results),
        "searched_at": datetime.datetime.utcnow().isoformat(),
        "error": error,
    }


# ---------------------------------------------------------------------------
# 4. search_failure_status
# ---------------------------------------------------------------------------

def search_failure_status(failure_status: str, org_nm: str = "") -> dict:
    """
    Search for the compliance meaning of an unknown FAILURE_STATUS string.

    Parameters
    ----------
    failure_status: str — the unknown failure status code/string
    org_nm        : str — organisation name for additional context (optional)

    Returns
    -------
    dict  — search result payload with trigger='unknown_failure_status'
    """
    query = (
        f"healthcare provider roster pipeline failure status "
        f"{failure_status} {org_nm} compliance meaning CMS"
    ).strip()

    error = None
    results = []
    try:
        results = _call_tavily(query, topic="general")
    except Exception as exc:
        error = str(exc)

    return {
        "trigger": "unknown_failure_status",
        "failure_status": failure_status,
        "org_nm": org_nm,
        "query": query,
        "results": results,
        "result_count": len(results),
        "searched_at": datetime.datetime.utcnow().isoformat(),
        "error": error,
    }


# ---------------------------------------------------------------------------
# 5. search_org_context
# ---------------------------------------------------------------------------

def search_org_context(
    org_nm: str,
    state: str = "",
    anomaly_type: str = "",
) -> dict:
    """
    Search for context about an organisation that appears as an anomaly.

    Parameters
    ----------
    org_nm      : str — organisation name
    state       : str — state for additional context (optional)
    anomaly_type: str — type of anomaly detected (optional)

    Returns
    -------
    dict  — search result payload with trigger='unknown_org_anomaly'
    """
    query = (
        f"healthcare provider organization {org_nm} {state} "
        f"Medicaid Medicare roster compliance issues"
    ).strip()

    error = None
    results = []
    try:
        results = _call_tavily(query, topic="general")
    except Exception as exc:
        error = str(exc)

    return {
        "trigger": "unknown_org_anomaly",
        "org_nm": org_nm,
        "state": state,
        "anomaly_type": anomaly_type,
        "query": query,
        "results": results,
        "result_count": len(results),
        "searched_at": datetime.datetime.utcnow().isoformat(),
        "error": error,
    }


# ---------------------------------------------------------------------------
# 6. format_search_results_for_prompt
# ---------------------------------------------------------------------------

def format_search_results_for_prompt(search_result: dict) -> str:
    """
    Format a search result dict into a clean string for LLM prompt injection.

    Parameters
    ----------
    search_result : dict — result from any of the 3 search functions

    Returns
    -------
    str — formatted multi-line string
    """
    trigger      = search_result.get("trigger", "unknown")
    query        = search_result.get("query", "")
    searched_at  = search_result.get("searched_at", "")
    results      = search_result.get("results", [])

    lines = [
        f"Web Search Results [{trigger}]",
        f"Query: {query}",
        f"Searched at: {searched_at}",
        "",
    ]

    if not results:
        lines.append("No results found.")
    else:
        for idx, item in enumerate(results, start=1):
            title   = item.get("title", "")
            url     = item.get("url", "")
            content = item.get("content", "")
            lines.append(f"[{idx}] {title}")
            lines.append(f"    URL: {url}")
            lines.append(f"    {content}")
            lines.append("")

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# 7. Master function — run_web_search
# ---------------------------------------------------------------------------

def run_web_search(trigger: str, params: dict) -> dict:
    """
    Route a web search request to the correct handler based on trigger type.

    Parameters
    ----------
    trigger : str  — one of: 'high_rejection_rate', 'unknown_failure_status',
                     'unknown_org_anomaly'
    params  : dict — keyword arguments for the target search function

    Returns
    -------
    dict — result from the appropriate search function, or error dict if
           TAVILY_API_KEY is not set or trigger is unknown.
    """
    # Guard: API key must be set
    if not TAVILY_API_KEY:
        return {
            "trigger": trigger,
            "results": [],
            "result_count": 0,
            "searched_at": datetime.datetime.utcnow().isoformat(),
            "error": "TAVILY_API_KEY not set",
        }

    if trigger == "high_rejection_rate":
        return search_regulatory_changes(
            state=params.get("state", ""),
            rejection_rate=params.get("rejection_rate", 0.0),
            lob=params.get("lob", ""),
        )

    if trigger == "unknown_failure_status":
        return search_failure_status(
            failure_status=params.get("failure_status", ""),
            org_nm=params.get("org_nm", ""),
        )

    if trigger == "unknown_org_anomaly":
        return search_org_context(
            org_nm=params.get("org_nm", ""),
            state=params.get("state", ""),
            anomaly_type=params.get("anomaly_type", ""),
        )

    # Unknown trigger
    return {
        "trigger": trigger,
        "results": [],
        "result_count": 0,
        "searched_at": datetime.datetime.utcnow().isoformat(),
        "error": f"Unknown trigger: '{trigger}'. "
                 f"Must be one of: high_rejection_rate, "
                 f"unknown_failure_status, unknown_org_anomaly.",
    }


# ---------------------------------------------------------------------------
# 8. Main test block — 3 trigger scenarios
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    if not TAVILY_API_KEY:
        print(
            "\n[WARNING] TAVILY_API_KEY is not set!\n"
            "Set it before running:\n"
            "  macOS/Linux : export TAVILY_API_KEY='tvly-...'\n"
            "  PowerShell  : $env:TAVILY_API_KEY='tvly-...'\n"
            "Get a free key at https://tavily.com (1000 searches/month free)\n"
        )

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

    print("\n" + "=" * 70)
    print("  RosterIQ — Web Search Test Suite (3 triggers via Tavily)")
    print("=" * 70 + "\n")

    for idx, case in enumerate(TEST_CASES, start=1):
        trigger = case["trigger"]
        params  = case["params"]

        print(f"[{idx}] Trigger : {trigger}")
        result = run_web_search(trigger, params)

        print(f"     Query   : {result.get('query', 'N/A')}")
        print(f"     Results : {result.get('result_count', 0)} returned")
        print(f"     Time    : {result.get('searched_at', 'N/A')}")

        if result.get("error"):
            print(f"     Error   : {result['error']}")
        elif result.get("results"):
            first = result["results"][0]
            content_preview = first.get("content", "")[:150].replace("\n", " ")
            print(f"     Top hit : {first.get('title', '')}")
            print(f"     Preview : {content_preview}...")
        else:
            print("     (no results)")

        print()

    print("=" * 70 + "\n")
