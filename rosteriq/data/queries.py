"""
RosterIQ SQL Query Library
All queries are parameterized. They target pre-aggregated tables for speed.
Returns Pandas DataFrames.
"""

import pandas as pd
from rosteriq.data.loader import get_connection, query_df


# ──────────────────────────────────────────────────────────────
# 1. Stuck / Stopped ROs
# ──────────────────────────────────────────────────────────────
def query_stuck_ros(
    state: str | None = None,
    org: str | None = None,
) -> pd.DataFrame:
    """SELECT from stuck_base, optionally filtered by state/org."""
    clauses, params = [], []
    if state:
        clauses.append("CNT_STATE = ?")
        params.append(state.upper())
    if org:
        clauses.append("ORG_NM LIKE ?")
        params.append(f"%{org}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM stuck_base {where} ORDER BY CNT_STATE, ORG_NM"
    return query_df(sql, tuple(params))


# ──────────────────────────────────────────────────────────────
# 2. Record Quality Audit
# ──────────────────────────────────────────────────────────────
def query_record_quality_audit(
    state: str | None = None,
    org: str | None = None,
) -> pd.DataFrame:
    """
    SELECT from audit_base, optionally filtered.
    Adds a boolean FLAG_LOW_QUALITY where SCS_PCT_FILE < 85.
    """
    clauses, params = [], []
    if state:
        clauses.append("CNT_STATE = ?")
        params.append(state.upper())
    if org:
        clauses.append("ORG_NM LIKE ?")
        params.append(f"%{org}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT *,
               CASE WHEN SCS_PCT_FILE < 85 THEN 1 ELSE 0 END AS FLAG_LOW_QUALITY
        FROM audit_base
        {where}
        ORDER BY SCS_PCT_FILE ASC
    """
    return query_df(sql, tuple(params))


# ──────────────────────────────────────────────────────────────
# 3. Retry Effectiveness
# ──────────────────────────────────────────────────────────────
def query_retry_effectiveness() -> pd.DataFrame:
    """
    Compare Run 1 vs Run 2+ for the same orgs from retry_base.
    Returns one row per org with run1 vs retry success rates.
    """
    sql = """
        SELECT
            r1.CNT_STATE,
            r1.ORG_NM,
            r1.TOT_FILE_CNT   AS RUN1_FILES,
            r1.SCS_PCT_FILE   AS RUN1_SCS_PCT,
            rn.RETRY_FILES,
            rn.RETRY_SCS_PCT,
            (rn.RETRY_SCS_PCT - r1.SCS_PCT_FILE) AS PCT_CHANGE
        FROM retry_base r1
        INNER JOIN (
            SELECT CNT_STATE, ORG_NM,
                   SUM(TOT_FILE_CNT)                         AS RETRY_FILES,
                   ROUND(SUM(SCS_CNT)*100.0/SUM(TOT_FILE_CNT), 2) AS RETRY_SCS_PCT
            FROM retry_base
            WHERE RUN_NO > 1
            GROUP BY CNT_STATE, ORG_NM
        ) rn ON r1.CNT_STATE = rn.CNT_STATE AND r1.ORG_NM = rn.ORG_NM
        WHERE r1.RUN_NO = 1
        ORDER BY PCT_CHANGE DESC
    """
    return query_df(sql)


# ──────────────────────────────────────────────────────────────
# 4. Cross-Table Health
# ──────────────────────────────────────────────────────────────
def query_cross_table_health(state: str) -> pd.DataFrame:
    """
    JOIN market_base with operational_metrics on State and Month
    to compare pipeline health against market success.
    """
    sql = """
        SELECT
            m.CNT_STATE,
            m.MONTH,
            m.TOT_FILE_CNT       AS PIPELINE_FILES,
            m.SCS_CNT            AS PIPELINE_SCS,
            m.FAIL_CNT           AS PIPELINE_FAIL,
            m.SCS_PCT_APPROX_AVG AS PIPELINE_HEALTH_PCT,
            o.OVERALL_SCS_CNT    AS MARKET_SCS_CNT,
            o.OVERALL_FAIL_CNT   AS MARKET_FAIL_CNT,
            o.SCS_PERCENT        AS MARKET_SCS_PCT
        FROM market_base m
        LEFT JOIN operational_metrics o
            ON m.CNT_STATE = o.MARKET
            AND m.MONTH     = o.MONTH
        WHERE m.CNT_STATE = ?
        ORDER BY m.MONTH
    """
    return query_df(sql, (state.upper(),))


# ──────────────────────────────────────────────────────────────
# 5. Stage Duration Anomalies
# ──────────────────────────────────────────────────────────────
def query_stage_duration_anomalies() -> pd.DataFrame:
    """
    Find rows in roster_enriched where any actual duration
    exceeds 2× its AVG counterpart.
    """
    sql = """
        SELECT
            ID, ORG_NM, CNT_STATE, LATEST_STAGE_NM,
            DART_GEN_DURATION,
            AVG_DART_GENERATION_DURATION,
            DART_UI_VALIDATION_DURATION,
            AVG_DART_UI_VLDTN_DURATION,
            SPS_LOAD_DURATION,
            AVG_SPS_LOAD_DURATION,
            ISF_GEN_DURATION,
            AVG_ISF_GENERATION_DURATION
        FROM roster_enriched
        WHERE (
            (DART_GEN_DURATION        > 2 * AVG_DART_GENERATION_DURATION
                AND AVG_DART_GENERATION_DURATION IS NOT NULL
                AND AVG_DART_GENERATION_DURATION > 0)
            OR
            (DART_UI_VALIDATION_DURATION > 2 * AVG_DART_UI_VLDTN_DURATION
                AND AVG_DART_UI_VLDTN_DURATION IS NOT NULL
                AND AVG_DART_UI_VLDTN_DURATION > 0)
            OR
            (SPS_LOAD_DURATION        > 2 * AVG_SPS_LOAD_DURATION
                AND AVG_SPS_LOAD_DURATION IS NOT NULL
                AND AVG_SPS_LOAD_DURATION > 0)
            OR
            (ISF_GEN_DURATION         > 2 * AVG_ISF_GENERATION_DURATION
                AND AVG_ISF_GENERATION_DURATION IS NOT NULL
                AND AVG_ISF_GENERATION_DURATION > 0)
        )
        ORDER BY DART_GEN_DURATION DESC
        LIMIT 500
    """
    return query_df(sql)


# ──────────────────────────────────────────────────────────────
# 6. Market Trend
# ──────────────────────────────────────────────────────────────
def query_market_trend(market: str, months: int = 6) -> pd.DataFrame:
    """
    Return monthly SCS_PERCENT for a market from operational_metrics,
    limited to the last N months by row order.
    """
    sql = """
        SELECT MONTH, MARKET, SCS_PERCENT,
               OVERALL_SCS_CNT, OVERALL_FAIL_CNT
        FROM operational_metrics
        WHERE MARKET = ?
        ORDER BY MONTH DESC
        LIMIT ?
    """
    return query_df(sql, (market.upper(), months))


# ──────────────────────────────────────────────────────────────
# 7. Generic SQL Fallback
# ──────────────────────────────────────────────────────────────
def execute_sql(sql_string: str, params: tuple = ()) -> pd.DataFrame:
    """Execute arbitrary read-only SQL. Use parameterized queries."""
    return query_df(sql_string, params)
