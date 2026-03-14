"""
derive_quality_metrics.py
Derives missing record-count metrics for the roster processing pipeline.
Combines file-level classification, state/month aggregation, and health-based SCS approximation.
"""

import pandas as pd
import numpy as np


def derive_quality_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Derive quality metrics from roster_processing_details data.

    Returns:
        enriched_df:  Original df with new file-level status columns + SCS_PCT_APPROX
        agg_df:       Aggregated counts by CNT_STATE × MONTH
    """
    df = df.copy()

    # ------------------------------------------------------------------
    # APPROACH 1 — File-level outcome classification
    # ------------------------------------------------------------------
    df['IS_SUCCESS'] = (df['LATEST_STAGE_NM'] == 'RESOLVED').astype(int)
    df['IS_STOP']    = (df['LATEST_STAGE_NM'] == 'STOPPED').astype(int)
    df['IS_REJ']     = (df['LATEST_STAGE_NM'] == 'REJECTED').astype(int)
    df['IS_SKIP']    = (df['FAILURE_STATUS'] == 'Incompatible').astype(int)
    df['IS_FAIL']    = (df['IS_FAILED'] == 1).astype(int)

    # ------------------------------------------------------------------
    # APPROACH 3 — Reverse-engineer SCS_PCT from health columns
    # ------------------------------------------------------------------
    health_cols = [
        'PRE_PROCESSING_HEALTH',
        'DART_GEN_HEALTH',
        'DART_REVIEW_HEALTH',
        'SPS_LOAD_HEALTH',
    ]
    existing_health = [c for c in health_cols if c in df.columns]
    df['ALL_GREEN'] = (df[existing_health] == 'Green').all(axis=1).astype(int)
    df['SCS_PCT_APPROX'] = (
        df.groupby('CNT_STATE')['ALL_GREEN']
        .transform('mean') * 100
    ).round(2)

    # ------------------------------------------------------------------
    # APPROACH 2 — Aggregate counts by State × Month
    # ------------------------------------------------------------------
    df['FILE_RECEIVED_DT'] = pd.to_datetime(df['FILE_RECEIVED_DT'], errors='coerce')
    df['MONTH'] = df['FILE_RECEIVED_DT'].dt.strftime('%m-%Y')

    agg_df = (
        df.groupby(['CNT_STATE', 'MONTH'])
        .agg(
            TOT_REC_CNT  = ('ID', 'count'),
            SCS_REC_CNT  = ('IS_SUCCESS', 'sum'),
            FAIL_REC_CNT = ('IS_FAIL', 'sum'),
            SKIP_REC_CNT = ('IS_SKIP', 'sum'),
            REJ_REC_CNT  = ('IS_REJ', 'sum'),
            STOP_REC_CNT = ('IS_STOP', 'sum'),
            AVG_SCS_PCT_APPROX = ('SCS_PCT_APPROX', 'mean'),
        )
        .reset_index()
    )
    agg_df['SCS_PCT'] = (
        agg_df['SCS_REC_CNT'] / agg_df['TOT_REC_CNT'] * 100
    ).round(2)

    return df, agg_df


# ======================================================================
# Run when executed directly
# ======================================================================
if __name__ == '__main__':
    print('Loading roster_processing_details.csv ...')
    raw = pd.read_csv('roster_processing_details.csv', low_memory=False)
    enriched, aggregated = derive_quality_metrics(raw)

    # Save enriched file-level data
    enriched.to_csv('roster_enriched.csv', index=False, na_rep='NaN')
    print(f'Saved roster_enriched.csv  ({enriched.shape[0]} rows x {enriched.shape[1]} cols)')

    # Save aggregated data
    aggregated.to_csv('roster_aggregated_metrics.csv', index=False)
    print(f'Saved roster_aggregated_metrics.csv  ({aggregated.shape[0]} rows x {aggregated.shape[1]} cols)')

    # Print summary
    print('\n' + '=' * 60)
    print('FILE-LEVEL STATUS COUNTS')
    print('=' * 60)
    for col in ['IS_SUCCESS', 'IS_STOP', 'IS_REJ', 'IS_SKIP', 'IS_FAIL']:
        print(f'  {col}: {enriched[col].sum():,}')

    print(f'\n{"=" * 60}')
    print('AGGREGATED METRICS SAMPLE (top 10 by TOT_REC_CNT)')
    print('=' * 60)
    top = aggregated.nlargest(10, 'TOT_REC_CNT')
    print(top.to_string(index=False))

    print(f'\n{"=" * 60}')
    print('SCS_PCT_APPROX BY STATE (health-based)')
    print('=' * 60)
    approx = enriched.groupby('CNT_STATE')['SCS_PCT_APPROX'].first().sort_values()
    print(approx.to_string())
