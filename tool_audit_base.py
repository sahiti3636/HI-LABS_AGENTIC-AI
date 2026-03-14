"""
tool_audit_base.py
Groups roster_enriched.csv by CNT_STATE × ORG_NM to create an org-level quality audit table.
"""

import pandas as pd

df = pd.read_csv('roster_enriched.csv', low_memory=False)

audit = (
    df.groupby(['CNT_STATE', 'ORG_NM'])
    .agg(
        TOT_FILE_CNT = ('ID', 'count'),
        SCS_CNT      = ('IS_SUCCESS', 'sum'),
        FAIL_CNT     = ('IS_FAIL', 'sum'),
        REJ_CNT      = ('IS_REJ', 'sum'),
        SKIP_CNT     = ('IS_SKIP', 'sum'),
    )
    .reset_index()
)

audit['SCS_PCT_FILE'] = (audit['SCS_CNT'] / audit['TOT_FILE_CNT'] * 100).round(2)

audit.to_csv('tool_audit_base.csv', index=False)

print(f'Saved tool_audit_base.csv  ({audit.shape[0]} rows x {audit.shape[1]} cols)')
print(f'\nTop 10 by file count:')
print(audit.nlargest(10, 'TOT_FILE_CNT').to_string(index=False))
print(f'\nBottom 10 by SCS_PCT_FILE (min 5 files):')
low = audit[audit['TOT_FILE_CNT'] >= 5].nsmallest(10, 'SCS_PCT_FILE')
print(low.to_string(index=False))
