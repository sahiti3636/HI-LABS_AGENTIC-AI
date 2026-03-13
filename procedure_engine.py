"""
procedure_engine.py
-------------------
Procedure execution engine for RosterIQ.

Loads procedures.json, executes named diagnostic procedures by
substituting parameters into SQL templates, and handles procedure
updates with changelog logging.

The 4 named procedures are:
    - triage_stuck_ros
    - record_quality_audit
    - market_health_report
    - retry_effectiveness_analysis

Person 2 calls:
    execute_procedure(name, params, conn)  — run a procedure
    list_procedures()                      — show available procedures
    update_procedure(name, field, value)   — update a procedure field
"""

import json
import sqlite3
from datetime import datetime

PROCEDURES_PATH = "procedures.json"


# ---------------------------------------------------------------------------
# 1. Load procedures
# ---------------------------------------------------------------------------

def load_procedures(path: str = PROCEDURES_PATH) -> dict:
    """
    Load procedures.json into memory.

    Returns:
        Dict of procedure definitions keyed by procedure name.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_procedures(procedures: dict, path: str = PROCEDURES_PATH) -> None:
    """
    Save updated procedures dict back to procedures.json.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(procedures, f, indent=4)


# ---------------------------------------------------------------------------
# 2. List available procedures
# ---------------------------------------------------------------------------

def list_procedures(path: str = PROCEDURES_PATH) -> list:
    """
    Returns a list of available procedure names and descriptions.

    Returns:
        List of dicts: [{"name": str, "description": str, "parameters": list}, ...]
    """
    procedures = load_procedures(path)
    return [
        {
            "name": name,
            "description": proc["description"],
            "parameters": proc["parameters"],
            "version": proc["version"]
        }
        for name, proc in procedures.items()
    ]


# ---------------------------------------------------------------------------
# 3. Select correct SQL template variant
# ---------------------------------------------------------------------------

def _select_sql_template(procedure: dict, params: dict) -> str:
    """
    Selects the correct SQL template variant based on provided parameters.

    Rules:
        - If all params are 'ALL', use the all_states or all_markets variant
        - Otherwise use the most specific variant available

    Args:
        procedure: The procedure definition dict.
        params:    Parameter dict e.g. {"state": "KS", "month": "ALL"}

    Returns:
        SQL string with parameters substituted.
    """
    templates = procedure["sql_template"]
    state = params.get("state", "ALL")
    month = params.get("month", "ALL")

    # Select variant
    if state == "ALL":
        if "all_states" in templates:
            sql = templates["all_states"]
        elif "all_markets" in templates:
            sql = templates["all_markets"]
        elif "all_states_market" in templates:
            sql = templates["all_states_market"]
        else:
            # Fall back to first available template
            sql = list(templates.values())[0]
    elif month != "ALL" and "by_state_and_month" in templates:
        sql = templates["by_state_and_month"]
    elif "by_state_all_months" in templates:
        sql = templates["by_state_all_months"]
    elif "by_state" in templates:
        sql = templates["by_state"]
    elif "market_level_by_state" in templates:
        sql = templates["market_level_by_state"]
    elif "ro_level_by_state" in templates:
        sql = templates["ro_level_by_state"]
    else:
        sql = list(templates.values())[0]

    # Substitute parameters
    for key, value in params.items():
        sql = sql.replace(f"{{{key}}}", value)

    return sql


# ---------------------------------------------------------------------------
# 4. Execute a procedure
# ---------------------------------------------------------------------------

def execute_procedure(
    procedure_name: str,
    params: dict,
    conn: sqlite3.Connection,
    path: str = PROCEDURES_PATH
) -> dict:
    """
    Executes a named procedure against the provided SQLite connection.

    Args:
        procedure_name: One of the 4 named procedures.
        params:         Parameter dict e.g. {"state": "KS"} or {"state": "ALL"}
        conn:           Active SQLite connection with ros and markets tables loaded.
        path:           Path to procedures.json.

    Returns:
        Dict with keys:
            "procedure_name": str
            "sql_executed": str
            "columns": list of column names
            "rows": list of dicts (one per result row)
            "row_count": int
            "interpretation_guidance": str
            "error": str or None
    """
    procedures = load_procedures(path)

    if procedure_name not in procedures:
        return {
            "procedure_name": procedure_name,
            "sql_executed": None,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "interpretation_guidance": "",
            "error": f"Procedure '{procedure_name}' not found. Available: {list(procedures.keys())}"
        }

    procedure = procedures[procedure_name]

    # Fill default params
    for param in procedure["parameters"]:
        if param not in params:
            params[param] = "ALL"

    sql = _select_sql_template(procedure, params)

    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows_as_dicts = [dict(row) for row in rows]

        return {
            "procedure_name": procedure_name,
            "sql_executed": sql,
            "columns": columns,
            "rows": rows_as_dicts,
            "row_count": len(rows_as_dicts),
            "interpretation_guidance": procedure["interpretation_guidance"],
            "error": None
        }

    except sqlite3.Error as e:
        return {
            "procedure_name": procedure_name,
            "sql_executed": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "interpretation_guidance": procedure["interpretation_guidance"],
            "error": str(e)
        }


# ---------------------------------------------------------------------------
# 5. Update a procedure (feedback-driven learning)
# ---------------------------------------------------------------------------

def update_procedure(
    procedure_name: str,
    field: str,
    new_value,
    change_description: str,
    path: str = PROCEDURES_PATH
) -> dict:
    """
    Updates a field in a named procedure and logs the change to changelog.

    Args:
        procedure_name:     Name of the procedure to update.
        field:              Field to update e.g. 'sql_template', 'description'
        new_value:          New value for the field.
        change_description: Human-readable description of what changed and why.
        path:               Path to procedures.json.

    Returns:
        Dict with keys:
            "success": bool
            "procedure_name": str
            "field_updated": str
            "old_value": any
            "new_value": any
            "version": int
            "changelog_entry": str
            "error": str or None
    """
    procedures = load_procedures(path)

    if procedure_name not in procedures:
        return {
            "success": False,
            "procedure_name": procedure_name,
            "field_updated": field,
            "old_value": None,
            "new_value": new_value,
            "version": None,
            "changelog_entry": None,
            "error": f"Procedure '{procedure_name}' not found."
        }

    procedure = procedures[procedure_name]
    old_value = procedure.get(field)

    # Apply update
    procedure[field] = new_value

    # Bump version
    procedure["version"] = procedure.get("version", 1) + 1
    procedure["last_modified"] = datetime.now().strftime("%Y-%m-%d")

    # Log changelog entry
    changelog_entry = (
        f"v{procedure['version']} [{procedure['last_modified']}]: "
        f"{change_description} (field: {field})"
    )
    procedure["changelog"].append(changelog_entry)

    # Save back to file
    save_procedures(procedures, path)

    print(f"[procedure_engine] Updated '{procedure_name}' to v{procedure['version']}: {change_description}")

    return {
        "success": True,
        "procedure_name": procedure_name,
        "field_updated": field,
        "old_value": old_value,
        "new_value": new_value,
        "version": procedure["version"],
        "changelog_entry": changelog_entry,
        "error": None
    }


# ---------------------------------------------------------------------------
# 6. Get procedure details
# ---------------------------------------------------------------------------

def get_procedure_details(
    procedure_name: str,
    path: str = PROCEDURES_PATH
) -> dict:
    """
    Returns full details of a named procedure including changelog.

    Args:
        procedure_name: Name of the procedure.

    Returns:
        Full procedure dict or error dict if not found.
    """
    procedures = load_procedures(path)
    if procedure_name not in procedures:
        return {"error": f"Procedure '{procedure_name}' not found."}
    return procedures[procedure_name]


# ---------------------------------------------------------------------------
# 7. __main__ test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import shutil

    print("=" * 62)
    print("RosterIQ - Procedure Engine Self-Test")
    print("=" * 62)

    # Use a copy of procedures.json so we don't corrupt the real one
    TEST_PROCEDURES_PATH = "procedures_test.json"
    shutil.copy(PROCEDURES_PATH, TEST_PROCEDURES_PATH)

    # ── 1. List procedures ────────────────────────────────────────
    print("\n[test] Available procedures:")
    for p in list_procedures(TEST_PROCEDURES_PATH):
        print(f"  - {p['name']} (v{p['version']}): {p['description'][:60]}...")

    # ── 2. Build a minimal in-memory SQLite DB for testing ────────
    print("\n[test] Building test SQLite DB...")
    conn = sqlite3.connect(":memory:")

    conn.execute("""
        CREATE TABLE ros (
            RO_ID TEXT, ORG_NM TEXT, CNT_STATE TEXT, LOB TEXT,
            LATEST_STAGE_NM TEXT, FILE_STATUS_CD TEXT,
            IS_STUCK INTEGER, IS_FAILED INTEGER, FAILURE_STATUS TEXT,
            DART_GEN_DURATION REAL, AVG_DART_GENERATION_DURATION REAL,
            PRE_PROCESSING_HEALTH TEXT, MAPPING_APROVAL_HEALTH TEXT,
            ISF_GEN_HEALTH TEXT, DART_GEN_HEALTH TEXT,
            DART_UI_VALIDATION_HEALTH TEXT, SPS_LOAD_HEALTH TEXT,
            health_score REAL, rejection_rate REAL, failure_rate REAL,
            dominant_problem TEXT, SRC_SYS TEXT, RUN_NO INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE markets (
            MARKET TEXT, MONTH TEXT, SCS_PERCENT REAL,
            below_threshold INTEGER, retry_lift REAL,
            FIRST_ITER_SCS_CNT INTEGER, FIRST_ITER_FAIL_CNT INTEGER,
            NEXT_ITER_SCS_CNT INTEGER, NEXT_ITER_FAIL_CNT INTEGER,
            OVERALL_SCS_CNT INTEGER, OVERALL_FAIL_CNT INTEGER
        )
    """)

    # Insert test RO rows
    conn.executemany(
        "INSERT INTO ros VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("RO-001","MercyOne","KS","Medicaid FFS","DART_GENERATION","49",
             1,0,"Complete Validation Failure",240.0,90.0,
             "Green","Green","Yellow","Red","Green","Green",
             25.0,0.41,0.12,"compliance","SYS-A",1),
            ("RO-002","KS Health Group","KS","Medicare HMO","SPS_LOAD","99",
             0,0,None,80.0,90.0,
             "Green","Green","Green","Green","Green","Yellow",
             70.0,0.15,0.05,"compliance","SYS-B",1),
            ("RO-003","FL Health Group","FL","Medicaid FFS","DART_GENERATION","49",
             1,0,"Schema Mismatch",200.0,95.0,
             "Green","Yellow","Red","Red","Green","Green",
             20.0,0.38,0.18,"compliance","SYS-A",2),
        ]
    )

    # Insert test market rows
    conn.executemany(
        "INSERT INTO markets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("KS","2026-01",79.0,1,1.12,800,200,90,110,890,310),
            ("KS","2026-02",71.0,1,1.08,750,250,80,120,830,370),
            ("FL","2026-01",68.0,1,1.05,600,400,50,150,650,550),
        ]
    )
    conn.commit()
    print("[test] Test DB ready with 3 ROs and 3 market rows.")

    # ── 3. Execute triage_stuck_ros ───────────────────────────────
    print("\n[test] Executing triage_stuck_ros for KS...")
    result = execute_procedure(
        "triage_stuck_ros",
        {"state": "KS"},
        conn,
        path=TEST_PROCEDURES_PATH
    )
    print(f"  SQL: {result['sql_executed'][:80]}...")
    print(f"  Rows returned: {result['row_count']}")
    print(f"  Error: {result['error']}")
    for row in result["rows"]:
        print(f"  >> RO_ID={row['RO_ID']} ORG={row['ORG_NM']} STUCK={row['IS_STUCK']} health={row['health_score']}")
    assert result["error"] is None
    assert result["row_count"] == 1
    print("  [PASS] triage_stuck_ros returned correct stuck RO.")

    # ── 4. Execute record_quality_audit ALL states ─────────────────
    print("\n[test] Executing record_quality_audit for ALL states...")
    result2 = execute_procedure(
        "record_quality_audit",
        {"state": "ALL"},
        conn,
        path=TEST_PROCEDURES_PATH
    )
    print(f"  Rows returned: {result2['row_count']}")
    print(f"  Error: {result2['error']}")
    for row in result2["rows"]:
        print(f"  >> ORG={row['ORG_NM']} rejection_rate={row['avg_rejection_rate']:.2f} problem={row['dominant_problem']}")
    assert result2["error"] is None
    print("  [PASS] record_quality_audit executed successfully.")

    # ── 5. Execute market_health_report ───────────────────────────
    print("\n[test] Executing market_health_report for KS all months...")
    result3 = execute_procedure(
        "market_health_report",
        {"state": "KS", "month": "ALL"},
        conn,
        path=TEST_PROCEDURES_PATH
    )
    print(f"  Rows returned: {result3['row_count']}")
    print(f"  Error: {result3['error']}")
    for row in result3["rows"]:
        print(f"  >> MARKET={row['MARKET']} MONTH={row['MONTH']} SCS={row['SCS_PERCENT']} below={row['below_threshold']}")
    assert result3["error"] is None
    print("  [PASS] market_health_report executed successfully.")

    # ── 6. Execute retry_effectiveness_analysis ───────────────────
    print("\n[test] Executing retry_effectiveness_analysis for KS...")
    result4 = execute_procedure(
        "retry_effectiveness_analysis",
        {"state": "KS"},
        conn,
        path=TEST_PROCEDURES_PATH
    )
    print(f"  Rows returned: {result4['row_count']}")
    print(f"  Error: {result4['error']}")
    assert result4["error"] is None
    print("  [PASS] retry_effectiveness_analysis executed successfully.")

    # ── 7. Test procedure update ──────────────────────────────────
    print("\n[test] Updating record_quality_audit description...")
    update_result = update_procedure(
        "record_quality_audit",
        "description",
        "Computes rejection and failure rates per organization. Now includes SKIP_REC_CNT in quality threshold per ops team request.",
        "Added SKIP_REC_CNT consideration per ops team feedback",
        path=TEST_PROCEDURES_PATH
    )
    print(f"  Success: {update_result['success']}")
    print(f"  New version: {update_result['version']}")
    print(f"  Changelog entry: {update_result['changelog_entry']}")
    assert update_result["success"] is True
    assert update_result["version"] == 2
    print("  [PASS] Procedure update and changelog working correctly.")

    # ── 8. Test unknown procedure ─────────────────────────────────
    print("\n[test] Testing unknown procedure name...")
    bad_result = execute_procedure(
        "nonexistent_procedure",
        {"state": "KS"},
        conn,
        path=TEST_PROCEDURES_PATH
    )
    assert bad_result["error"] is not None
    print(f"  Error correctly returned: {bad_result['error']}")
    print("  [PASS] Unknown procedure handled gracefully.")

    # ── Cleanup ───────────────────────────────────────────────────
    conn.close()
    os.remove(TEST_PROCEDURES_PATH)
    print("\n[OK] All procedure engine tests passed.")
    print("=" * 62)