"""
RosterIQ Configuration
CSV-to-table mappings and project paths.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Base directory where CSVs live
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '')

# CSV filename → SQLite table name
TABLE_MAP = {
    'roster_enriched.csv':                    'roster_enriched',
    'aggregated_operational_metrics.csv':      'operational_metrics',
    'tool_audit_base.csv':                    'audit_base',
    'tool_retry_base.csv':                    'retry_base',
    'tool_market_base.csv':                   'market_base',
    'tool_stuck_base.csv':                    'stuck_base',
}

# SQLite DB path (":memory:" for in-memory)
SQLITE_DB = ':memory:'
