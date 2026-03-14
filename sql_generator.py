"""
sql_generator.py
================
RosterIQ — AI agent that diagnoses healthcare provider roster pipeline failures.
Generates SQL from natural language via Gemini API.
"""

import json
import os
import re
import sqlite3
import sys
import time
from dotenv import load_dotenv
load_dotenv()
import requests

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------

# Support both GEMINI_API_KEY (legacy) and GOOGLE_API_KEY (rosteriq)
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_URL: str = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
MODEL_NAME: str = "gemini-flash-latest"
RATE_LIMIT_DELAY: float = 2.0  # Safe delay for free tier


# ---------------------------------------------------------------------------
# 2. Schema string builder
# ---------------------------------------------------------------------------

def build_schema_string() -> str:
    schema = """
CREATE TABLE ros (
    ID                           INTEGER,
    RO_ID                        TEXT,
    RA_FILE_DETAILS_ID           TEXT,
    RA_ROSTER_DETAILS_ID         TEXT,
    RA_PLM_RO_PROF_DATA_ID       TEXT,
    SRC_SYS                      TEXT,
    ORG_NM                       TEXT,
    RUN_NO                       INTEGER,
    CNT_STATE                    TEXT,
    LOB                          TEXT,
    FILE_RECEIVED_DT             TEXT,
    FILE_STATUS_CD               TEXT,
    LATEST_STAGE_NM              TEXT,
    RA_PLM_RO_FILE_DATA_CREATION TEXT,
    PRE_PROCESSING_START_DT      TEXT,
    PRE_PROCESSING_END_DT        TEXT,
    MAPPING_APPRVD_AT            TEXT,
    ISF_GEN_START_DT             TEXT,
    ISF_GEN_END_DT               TEXT,
    DART_GEN_START_DT            TEXT,
    DART_GEN_END_DT              TEXT,
    RELEASED_TO_DART_UI_DT       TEXT,
    DART_UI_VALIDATION_START_DT  TEXT,
    DART_UI_VALIDATION_END_DT    TEXT,
    SPS_LOAD_START_DT            TEXT,
    SPS_LOAD_END_DT              TEXT,
    PRE_PROCESSING_DURATION      REAL,
    MAPPING_APROVAL_DURATION     REAL,
    ISF_GEN_DURATION             REAL,
    DART_GEN_DURATION            REAL,
    DART_REVIEW_DURATION         REAL,
    DART_UI_VALIDATION_DURATION  REAL,
    SPS_LOAD_DURATION            REAL,
    AVG_DART_GENERATION_DURATION REAL,
    AVG_DART_UI_VLDTN_DURATION   REAL,
    AVG_SPS_LOAD_DURATION        REAL,
    AVG_ISF_GENERATION_DURATION  REAL,
    PRE_PROCESSING_HEALTH        TEXT,
    MAPPING_APROVAL_HEALTH       TEXT,
    ISF_GEN_HEALTH               TEXT,
    DART_GEN_HEALTH              TEXT,
    DART_REVIEW_HEALTH           TEXT,
    DART_UI_VALIDATION_HEALTH    TEXT,
    SPS_LOAD_HEALTH              TEXT,
    IS_STUCK                     INTEGER,
    RA_BTCH_RUN_ID               TEXT,
    IS_FAILED                    INTEGER,
    FAILURE_STATUS               TEXT,
    LATEST_OBJECT_RUN_DT         TEXT,
    CREAT_DT                     TEXT,
    CREAT_USER_ID                TEXT,
    LAST_UPDT_DT                 TEXT,
    LAST_UPDT_USER_ID            TEXT,
    -- derived columns added at runtime
    rejection_rate               REAL,
    failure_rate                 REAL,
    health_score                 REAL,
    is_anomaly                   INTEGER,
    dominant_problem             TEXT
);

CREATE TABLE markets (
    ID                  INTEGER,
    MONTH               TEXT,
    MARKET              TEXT,
    CLIENT_ID           TEXT,
    FIRST_ITER_SCS_CNT  INTEGER,
    FIRST_ITER_FAIL_CNT INTEGER,
    NEXT_ITER_SCS_CNT   INTEGER,
    NEXT_ITER_FAIL_CNT  INTEGER,
    OVERALL_SCS_CNT     INTEGER,
    OVERALL_FAIL_CNT    INTEGER,
    SCS_PERCENT         REAL,
    IS_ACTIVE           INTEGER,
    CREAT_DT            TEXT,
    CREAT_USER_ID       TEXT,
    LAST_UPDT_DT        TEXT,
    LAST_UPDT_USER_ID   TEXT,
    -- derived columns added at runtime
    below_threshold     INTEGER,
    retry_lift          REAL,
    trend_direction     TEXT
);

-- Join condition: ros.CNT_STATE = markets.MARKET
-- Key derived columns:
--   rejection_rate  = REJ_REC_CNT / TOT_REC_CNT
--   failure_rate    = FAIL_REC_CNT / TOT_REC_CNT
--   health_score    = weighted composite score
--   below_threshold = 1 if SCS_PERCENT < 85
""".strip()
    return schema


# ---------------------------------------------------------------------------
# 3. Prompt builder
# ---------------------------------------------------------------------------

def build_sql_prompt(natural_language_query: str, schema: str) -> dict:
    system_prompt = (
        "You are an expert SQL generator for a healthcare provider roster pipeline system.\n"
        "You must return ONLY a valid SQLite SQL query, nothing else.\n"
        "No explanations, no markdown, no code blocks, just raw SQL.\n"
        "Always use table aliases (r for ros, m for markets).\n"
        "When joining tables use: ros r LEFT JOIN markets m ON r.CNT_STATE = m.MARKET\n"
        "Never hallucinate column names — only use columns that exist in the schema.\n"
        "Always end the query with a semicolon."
    )

    user_prompt = (
        f"Database Schema:\n{schema}\n\n"
        f"Question: {natural_language_query}\n\n"
        "Return ONLY the SQL query, no explanation."
    )

    return {"system": system_prompt, "user": user_prompt}


# ---------------------------------------------------------------------------
# 4. LLM call
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove ⁠ sql ...  ⁠ or ⁠  ...  ⁠ fences if present."""
    text = re.sub(r"^⁠  [a-zA-Z]*\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"  ⁠\s*$", "", text.strip())
    return text.strip()


def call_llm_for_sql(natural_language_query: str, retry_context: str = "") -> str:
    schema = build_schema_string()
    prompts = build_sql_prompt(natural_language_query, schema)

    user_message = prompts["user"]
    if retry_context:
        user_message = retry_context + "\n\n" + user_message

    headers = {
        "Content-Type": "application/json",
    }

    url = GEMINI_URL.format(MODEL_NAME) + f"?key={GEMINI_API_KEY}"

    payload = {
        "systemInstruction": {
            "parts": [{"text": prompts["system"]}]
        },
        "contents": [{
            "parts": [{"text": user_message}]
        }],
        "generationConfig": {
            "maxOutputTokens": 500,
            "temperature": 0.0,
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini API error {response.status_code}: {response.text}"
        )

    data = response.json()

    try:
        raw_sql = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"Unexpected API response structure: {json.dumps(data)}"
        ) from exc

    clean_sql = _strip_markdown_fences(raw_sql).strip()
    return clean_sql


# ---------------------------------------------------------------------------
# 5. SQL validation
# ---------------------------------------------------------------------------

def validate_sql(sql: str) -> bool:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("EXPLAIN " + sql)
        conn.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 6. Master generate function
# ---------------------------------------------------------------------------

def generate_sql(natural_language_query: str) -> dict:
    was_retried = False
    sql = ""
    is_valid = False

    # --- Attempt 1 ---
    try:
        sql = call_llm_for_sql(natural_language_query)
        is_valid = validate_sql(sql)
    except Exception as exc:
        sql = f"-- ERROR: {exc}"
        is_valid = False

    # --- Attempt 2 (retry if first was invalid) ---
    if not is_valid:
        was_retried = True
        time.sleep(RATE_LIMIT_DELAY)
        retry_context = (
            "The previous SQL query you generated was invalid or failed SQLite syntax validation.\n"
            "Please carefully re-read the schema and generate a corrected SQL query.\n"
            f"Previous (invalid) SQL:\n{sql}\n"
        )
        try:
            sql = call_llm_for_sql(natural_language_query, retry_context=retry_context)
            is_valid = validate_sql(sql)
        except Exception as exc:
            sql = f"-- ERROR on retry: {exc}"
            is_valid = False

    return {
        "sql": sql,
        "is_valid": is_valid,
        "was_retried": was_retried,
        "needs_human_review": was_retried and not is_valid,
        "query": natural_language_query,
    }


# ---------------------------------------------------------------------------
# 7. Main test block — 10 diagnostic queries
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    if not GEMINI_API_KEY:
        print(
            "\n[WARNING] GEMINI_API_KEY is not set!\n"
            "Set it before running:\n"
            "  macOS/Linux : export GEMINI_API_KEY='your_key_here'\n"
            "  PowerShell  : $env:GEMINI_API_KEY='your_key_here'\n"
        )
    else:
        print(f"[INFO] GEMINI_API_KEY found ({GEMINI_API_KEY[:7]}...)")

    TEST_QUERIES = [
        "How many ROs are currently stuck?",
        "Show me all failed ROs in Kansas",
        "What is the rejection rate for each organization?",
        "Which pipeline stage has the most anomalies?",
        "Show me ROs stuck in DART generation stage",
        "What is the average health score per state?",
        "Which markets are below the success threshold?",
        "Show me the top 5 organizations by failure rate",
        "How many ROs does each source system have?",
        "Why is the Kansas market below threshold — correlate with RO rejection rates?",
    ]

    first_attempt_valid = 0
    retried_count = 0
    human_review_count = 0
    total_api_calls = 0

    print("\n" + "=" * 72)
    print("  RosterIQ — SQL Generator Test Suite (10 queries via Gemini)")
    print("=" * 72 + "\n")

    results = []
    for idx, query in enumerate(TEST_QUERIES, start=1):
        print(f"[{idx:02d}] {query}")

        if idx > 1:
            time.sleep(RATE_LIMIT_DELAY)

        result = generate_sql(query)

        sql_preview = result["sql"][:120].replace("\n", " ")
        ellipsis = "..." if len(result["sql"]) > 120 else ""
        print(f"     SQL             : {sql_preview}{ellipsis}")
        print(f"     is_valid        : {result['is_valid']}")
        print(f"     was_retried     : {result['was_retried']}")
        print(f"     needs_human_review: {result['needs_human_review']}")
        print()

        results.append(result)

        if result["is_valid"] and not result["was_retried"]:
            first_attempt_valid += 1
        if result["was_retried"]:
            retried_count += 1
            total_api_calls += 2
        else:
            total_api_calls += 1
        if result["needs_human_review"]:
            human_review_count += 1

    print("=" * 72)
    print(f"  {first_attempt_valid}/10  valid on first attempt")
    print(f"  {retried_count}/10  needed retry")
    print(f"  {human_review_count}/10  need human review")
    print(f"  {total_api_calls}    total API calls made")
    print("=" * 72 + "\n")