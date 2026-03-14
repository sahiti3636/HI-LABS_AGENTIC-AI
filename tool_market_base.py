"""
tool_market_base.py
Groups roster_enriched.csv by CNT_STATE × MONTH for market-level correlation analysis.
"""

import pandas as pd

df = pd.read_csv('roster_enriched.csv', low_memory=False)

market = (
    df.groupby(['CNT_STATE', 'MONTH'])
    .agg(
        TOT_FILE_CNT       = ('ID', 'count'),
        SCS_CNT            = ('IS_SUCCESS', 'sum'),
        FAIL_CNT           = ('IS_FAIL', 'sum'),
        REJ_CNT            = ('IS_REJ', 'sum'),
        SCS_PCT_APPROX_AVG = ('SCS_PCT_APPROX', 'mean'),
    )
    .reset_index()
)

market['SCS_PCT_APPROX_AVG'] = market['SCS_PCT_APPROX_AVG'].round(2)

market.to_csv('tool_market_base.csv', index=False)

print(f'Saved tool_market_base.csv  ({market.shape[0]} rows x {market.shape[1]} cols)')
print(f'\nSample (top 10 by TOT_FILE_CNT):')
print(market.nlargest(10, 'TOT_FILE_CNT').to_string(index=False))
