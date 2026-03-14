"""
tool_retry_base.py
Groups roster_enriched.csv by CNT_STATE × ORG_NM × RUN_NO to analyze retry effectiveness.
"""

import pandas as pd

df = pd.read_csv('roster_enriched.csv', low_memory=False)

retry = (
    df.groupby(['CNT_STATE', 'ORG_NM', 'RUN_NO'])
    .agg(
        TOT_FILE_CNT = ('ID', 'count'),
        SCS_CNT      = ('IS_SUCCESS', 'sum'),
    )
    .reset_index()
)

retry['SCS_PCT_FILE'] = (retry['SCS_CNT'] / retry['TOT_FILE_CNT'] * 100).round(2)

retry.to_csv('tool_retry_base.csv', index=False)

print(f'Saved tool_retry_base.csv  ({retry.shape[0]} rows x {retry.shape[1]} cols)')
print(f'\nRUN_NO distribution:')
print(retry.groupby('RUN_NO')['TOT_FILE_CNT'].sum().to_string())
print(f'\nSample — Run 1 vs Run 2+ for top orgs:')
top_orgs = retry.groupby('ORG_NM')['TOT_FILE_CNT'].sum().nlargest(5).index
sample = retry[retry['ORG_NM'].isin(top_orgs)].sort_values(['ORG_NM', 'RUN_NO'])
print(sample.to_string(index=False))
