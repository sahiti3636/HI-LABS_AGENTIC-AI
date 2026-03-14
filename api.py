from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
import uvicorn
from person4_master import run_full_query, get_person4_status, get_dashboard_stats
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RosterIQ API Bridge")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "p4-default"

class ChatResponse(BaseModel):
    query: str
    intent: str
    answer: str
    data: Any
    reasoning: Optional[str] = None
    sources: List[str] = []
    chart_hint: Optional[str] = None
    chart_data: Optional[Any] = None
    exec_time_sec: float

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = run_full_query(request.query, session_id=request.session_id)
        # Ensure all fields expected by the response model are present
        return {
            "query": result.get("query", request.query),
            "intent": result.get("intent", "unknown"),
            "answer": result.get("answer", ""),
            "data": result.get("data"),
            "reasoning": result.get("reasoning"),
            "sources": result.get("sources", []),
            "chart_hint": result.get("chart_hint"),
            "chart_data": result.get("chart_data"),
            "exec_time_sec": result.get("exec_time_sec", 0.0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard-stats")
async def dashboard_stats():
    return get_dashboard_stats()

@app.get("/api/status")
async def status():
    return get_person4_status()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
