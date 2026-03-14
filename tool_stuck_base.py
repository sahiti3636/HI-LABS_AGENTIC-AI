"""
tool_stuck_base.py
Filters roster_enriched.csv for stuck/stopped operations for triage.
"""

import pandas as pd

df = pd.read_csv('roster_enriched.csv', low_memory=False)

stuck = df[(df['IS_STUCK'] == 1) | (df['IS_STOP'] == 1)]

cols = [
    'ID', 'ORG_NM', 'CNT_STATE', 'LATEST_STAGE_NM',
    'PRE_PROCESSING_HEALTH', 'DART_GEN_HEALTH',
    'DART_REVIEW_HEALTH', 'SPS_LOAD_HEALTH',
]

stuck = stuck[cols]

stuck.to_csv('tool_stuck_base.csv', index=False)

print(f'Saved tool_stuck_base.csv  ({stuck.shape[0]} rows x {stuck.shape[1]} cols)')
print(f'\nLATEST_STAGE_NM breakdown:')
print(stuck['LATEST_STAGE_NM'].value_counts().to_string())
print(f'\nHealth distributions:')
for h in ['PRE_PROCESSING_HEALTH', 'DART_GEN_HEALTH', 'DART_REVIEW_HEALTH', 'SPS_LOAD_HEALTH']:
    print(f'  {h}: {stuck[h].value_counts().to_dict()}')
print(f'\nTop 10 orgs by stuck/stopped count:')
print(stuck['ORG_NM'].value_counts().head(10).to_string())
