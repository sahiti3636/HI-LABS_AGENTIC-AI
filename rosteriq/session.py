"""
RosterIQ Session Management
Manages conversation history, start times, and query metrics.
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    query_count: int = 0
    history: list[dict] = field(default_factory=list)
    context_data: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata):
        """Append a message to the rolling history."""
        self.history.append({
            'role': role,
            'content': content,
            'timestamp': time.time(),
            **metadata
        })
        # Keep rolling history (last 10 queries = 20 messages roughly, 
        # but user specifically asked for last 10 queries).
        # We'll keep last 20 messages to cover roughly 10 turns.
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def increment_query(self):
        self.query_count += 1

    def get_context(self) -> dict[str, Any]:
        """Return session-specific metadata for context assembly."""
        return {
            "session_id": self.session_id,
            "query_count": self.query_count,
            "uptime_sec": round(time.time() - self.start_time, 2),
            **self.context_data
        }

    def update_data(self, key: str, value: Any):
        self.context_data[key] = value


# Active sessions store
_sessions: dict[str, Session] = {}


def get_or_create_session(session_id: Optional[str] = None) -> Session:
    """Retrieve an existing session or create a new one with a start timestamp."""
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    
    new_id = session_id or str(uuid.uuid4())
    session = Session(session_id=new_id)
    _sessions[new_id] = session
    return session


def get_session_context(session_id: str) -> dict:
    """External accessor for session context."""
    return get_or_create_session(session_id).get_context()


def update_session(session_id: str, key: str, value: Any):
    """External accessor for updating session data."""
    get_or_create_session(session_id).update_data(key, value)
