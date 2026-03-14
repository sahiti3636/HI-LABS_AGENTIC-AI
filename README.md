# 🏥 RosterIQ: Autonomous Healthcare Roster Agent

Welcome to **RosterIQ**, an intelligent, autonomous agent designed to optimize, monitor, and diagnose healthcare provider roster pipelines. Through an innovative multi-agent architecture, RosterIQ leverages natural language understanding to empower operational teams to proactively manage pipeline failures, track anomalies, and seamlessly integrate insights into their workflow.

---

## ✨ Key Features

- **🧠 Intelligent Query Routing & Intent Classification**
  Translates natural language questions into executable actions. Using a custom fine-tuned NLP model (or fallback heuristics), it identifies if a user wants a data query, global statistics, a visualization, a procedure run, or a memory recall.
- **📊 Natural Language to SQL (NL2SQL)**
  Automatically writes complex SQL queries to extract pipeline metrics (e.g., success rates, stuck volume) out of datasets. Powered by Gemini.
- **🌐 Web Search Diagnostics & Episodic Memory**
  Automatically triggers web searches (via Tavily) for external context when anomalies are detected (e.g., "high rejection rate in KS"). It logs findings to an episodic memory SQLite database, allowing the agent to remember and reference past triage events.
- **⚙️ Automated Procedure Engine**
  Defines and executes structured operational procedures (stored in `procedures.json`) for analyzing stuck files and triaging provider data.
- **📈 Real-Time Live Dashboard & Chat Console**
  A sleek frontend application (`hi-labs-frontend`) powered by a FastAPI backend (`api.py`). The dashboard shows live metrics (total files, success rates, stuck files, and system uptime) alongside a chat interface to directly interrogate the agent.

---

## 🏗️ Architecture Overview

RosterIQ is built using a decoupled, agentic architecture:

- **Frontend (`hi-labs-frontend/`)**: The user interface featuring the Chat Console and Live Dashboard.
- **API Bridge (`api.py`)**: A FastAPI web server connecting the frontend to the agentic backend.
- **Master Orchestrator (`person4_master.py`)**: The central routing system that determines how queries should be handled and orchestrates the underlying tools.
- **Agentic Tools**:
  - `intent_classifier.py`: Determines the user's goal via NLP.
  - `sql_generator.py`: Converts queries into SQL against the database map.
  - `web_search.py` & `web_search_logger.py`: Gathers external insights and persists them.
  - `episodic_memory.py` & `semantic_store.py`: Provides long-term diagnostic memory and vector embeddings.
  - `procedure_engine.py`: Runs multi-step analytical jobs.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Node.js & npm (for the frontend)
- API Keys: 
  - `GEMINI_API_KEY` (for SQL generation & reasoning)
  - `TAVILY_API_KEY` (for web search)

### Backend Setup

1. **Clone the repository** and navigate to the root directory.
2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Create a requirements.txt if not already present, ensuring libraries like fastapi, uvicorn, python-dotenv, etc., are included.)*

3. **Configure the environment**:
   Edit or create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   TAVILY_API_KEY=your_tavily_api_key
   ```

4. **Start the FastAPI Backend**:
   ```bash
   python api.py
   ```
   The backend will be available at `http://127.0.0.1:8000`.

### Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd hi-labs-frontend
   ```
2. **Install Node dependencies**:
   ```bash
   npm install
   ```
3. **Start the development server**:
   ```bash
   npm run dev
   ```
   *Your app should now be running in your browser.*

---

## 💻 Usage

- **Chat Interface**: Open the application to chat with the agent. Ask questions like:
  - *"How many ROs are currently stuck in Kansas?"*
  - *"Show me the top 5 organizations by failure rate."*
  - *"What did we find last time about Kansas?"*
- **Dashboard**: Monitor the "Market Health", total files processed, success rates, and live recent activity extracted from the agent's episodic memory.

---

## 📂 Project Structure

```text
├── api.py                    # FastAPI bridge
├── person4_master.py         # Primary orchestrator
├── intent_classifier.py      # NLP router
├── sql_generator.py          # NL-to-SQL logic
├── procedure_engine.py       # Automated procedures
├── web_search.py             # Web search tool
├── web_search_logger.py      # Web search logger
├── episodic_memory.py        # SQLite episodic memory
├── episodic_recall.py        # Memory recall utility
├── semantic_store.py         # Vector semantic store
├── embedding_store.py        # Embedding utility
├── derive_quality_metrics.py # Quality metrics utility
├── generate_training_data.py # Training data generation
├── train_intent_classifier.py# Intent model training script
├── hi-labs-frontend/         # Next.js UI Frontend
├── procedures.json           # Defined Agent procedures
├── domain_knowledge.json     # Domain knowledge mapping
├── training_data.json        # Intent training data
├── roster_enriched.csv       # Main data file
├── tool_audit_base.csv       # Audit data
├── tool_market_base.csv      # Market data
├── tool_retry_base.csv       # Retry data
├── tool_stuck_base.csv       # Stuck records data
└── aggregated_operational_metrics.csv # Metrics data
```

---
