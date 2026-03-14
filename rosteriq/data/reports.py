"""
RosterIQ Report Generator
Combines query functions into a single structured report.
"""

from rosteriq.data.queries import (
    query_stuck_ros,
    query_record_quality_audit,
    query_retry_effectiveness,
    query_cross_table_health,
    query_stage_duration_anomalies,
    query_market_trend,
)
from rosteriq.context import get_global_vars


def generate_report(
    state: str | None = None,
    org: str | None = None,
    time_window: int | None = None,
) -> dict:
    """
    Generate a comprehensive quality report.

    Args:
        state:        Filter by state (e.g. 'CA')
        org:          Filter by org name substring
        time_window:  Number of months for trend (default 6)

    Returns dict with keys:
        summary_stats, flagged_ros, stage_bottlenecks,
        record_quality, market_scs, recommended_actions
    """
    months = time_window or 6
    gv = get_global_vars()

    # ── 1. Summary Stats ────────────────────────────────────
    summary_stats = {**gv}

    # ── 2. Flagged ROs (stuck / stopped) ────────────────────
    stuck_df = query_stuck_ros(state=state, org=org)
    flagged_ros = {
        'total': len(stuck_df),
        'by_stage': stuck_df['LATEST_STAGE_NM'].value_counts().to_dict() if len(stuck_df) else {},
        'by_health': {},
        'sample': stuck_df.head(20).to_dict(orient='records'),
    }
    for h in ['PRE_PROCESSING_HEALTH', 'DART_GEN_HEALTH', 'DART_REVIEW_HEALTH', 'SPS_LOAD_HEALTH']:
        if h in stuck_df.columns:
            flagged_ros['by_health'][h] = stuck_df[h].value_counts().to_dict()

    # ── 3. Stage Bottlenecks (duration anomalies) ───────────
    anomalies_df = query_stage_duration_anomalies()
    bottleneck_counts = {}
    if len(anomalies_df):
        for col_pair in [
            ('DART_GEN_DURATION', 'AVG_DART_GENERATION_DURATION'),
            ('SPS_LOAD_DURATION', 'AVG_SPS_LOAD_DURATION'),
            ('ISF_GEN_DURATION', 'AVG_ISF_GENERATION_DURATION'),
            ('DART_UI_VALIDATION_DURATION', 'AVG_DART_UI_VLDTN_DURATION'),
        ]:
            actual, avg = col_pair
            mask = (
                anomalies_df[actual].notna()
                & anomalies_df[avg].notna()
                & (anomalies_df[avg] > 0)
                & (anomalies_df[actual] > 2 * anomalies_df[avg])
            )
            bottleneck_counts[actual] = int(mask.sum())

    stage_bottlenecks = {
        'anomaly_count': len(anomalies_df),
        'by_stage': bottleneck_counts,
        'top_offenders': (
            anomalies_df
            .groupby('CNT_STATE')['ID']
            .count()
            .nlargest(5)
            .to_dict()
        ) if len(anomalies_df) else {},
    }

    # ── 4. Record Quality ───────────────────────────────────
    quality_df = query_record_quality_audit(state=state, org=org)
    flagged_quality = quality_df[quality_df['FLAG_LOW_QUALITY'] == 1] if len(quality_df) else quality_df
    record_quality = {
        'total_orgs': len(quality_df),
        'flagged_count': len(flagged_quality),
        'flagged_pct': round(len(flagged_quality) / len(quality_df) * 100, 2) if len(quality_df) else 0,
        'worst_10': flagged_quality.head(10).to_dict(orient='records'),
    }

    # ── 5. Market SCS ──────────────────────────────────────
    market_scs = {}
    if state:
        trend_df = query_market_trend(state, months)
        market_scs = {
            'market': state.upper(),
            'months': len(trend_df),
            'trend': trend_df.to_dict(orient='records'),
        }
        cross_df = query_cross_table_health(state)
        if len(cross_df):
            market_scs['cross_table'] = cross_df.to_dict(orient='records')

    # ── 6. Recommended Actions ─────────────────────────────
    actions = _derive_actions(flagged_ros, stage_bottlenecks, record_quality, market_scs)

    return {
        'summary_stats':      summary_stats,
        'flagged_ros':        flagged_ros,
        'stage_bottlenecks':  stage_bottlenecks,
        'record_quality':     record_quality,
        'market_scs':         market_scs,
        'recommended_actions': actions,
    }


def _derive_actions(flagged_ros: dict, bottlenecks: dict, quality: dict, market: dict) -> list[str]:
    """Rule-based action recommendations."""
    actions = []

    # Stuck files
    if flagged_ros['total'] > 100:
        actions.append(
            f"CRITICAL: {flagged_ros['total']} stuck/stopped files. "
            f"Prioritize DART_REVIEW stage (highest Red health count)."
        )

    # Duration anomalies
    if bottlenecks.get('anomaly_count', 0) > 50:
        worst_stage = max(bottlenecks.get('by_stage', {}), key=bottlenecks['by_stage'].get, default=None)
        if worst_stage:
            actions.append(
                f"WARNING: {bottlenecks['anomaly_count']} duration anomalies detected. "
                f"Worst stage: {worst_stage} ({bottlenecks['by_stage'][worst_stage]} violations)."
            )

    # Quality flags
    if quality.get('flagged_pct', 0) > 50:
        actions.append(
            f"QUALITY: {quality['flagged_pct']}% of orgs below 85% success. "
            f"Review bottom performers for systemic issues."
        )

    # Market trend
    if market.get('trend'):
        trend = market['trend']
        if len(trend) >= 2:
            latest = trend[0].get('SCS_PERCENT', 0) or 0
            prev = trend[1].get('SCS_PERCENT', 0) or 0
            if latest < prev:
                actions.append(
                    f"TREND: {market['market']} SCS dropped from {prev}% to {latest}% "
                    f"in the latest month."
                )

    if not actions:
        actions.append("No critical issues detected.")

    return actions
