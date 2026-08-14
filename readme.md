# Baxter: Requirement & Test Case Automation Engine

Baxter is an enterprise-grade automated pipeline that parses Functional Requirements Documents (FRD) and Manual Test Cases (via direct file upload or Jira Cloud integration), maps them using AST/fuzzy matching algorithms, and leverages LLM agents to generate BDD Cucumber scenarios, Selenium pytest scripts, and CSV execution step matrices.

The project features a **FastAPI backend** interfacing with modular Python agent pipelines and a modern **React + Vite frontend** with real-time progress metrics and batch streaming.

---

## 🚀 Key Features

* **Jira Cloud Ingestion & AI Attachment Evaluation:** Connects securely to Jira Cloud, extracts Epics, and intelligently classifies attachments into FRDs and Manual Test Cases before downloading them for execution.
* **Dual-Document AST Parsing:** Automatically extracts and links structured requirements from FRDs and manual test documents (`.docx`).
* **Fuzzy Subject-to-Feature Mapping:** Integrates a 3-tier matching engine (substring matching, word overlap, and Levenshtein distance) to dynamically bind tests to requirements.
* **Unified Single-Chain Code Generation:** Utilizes a Pydantic-structured prompt chain to generate Cucumber (`.feature`), Selenium (`pytest` / `.py`), and CSV steps in a single, aligned, cost-effective LLM call.
* **Multi-FRD Batch Orchestrator:** Parallel processing with Server-Sent Events (SSE) live progress streaming and batch ZIP exports.
* **Production Web UI Dashboard:** Responsive React interface tracking real-time pipeline status, stopwatch timings, test case metrics, and in-memory ZIP downloads.

---

## 🛠️ Project Structure

```text
Baxter/
├── agents/
│   ├── doc_parser.py     # Document Parsing & Context Enrichment Agent
│   ├── scanners.py       # Word document table extraction & classification
│   ├── jira_agent.py     # Jira Cloud API client & attachment processor
│   ├── jira_prompts.py   # LLM prompts for Jira attachment classification
│   └── __init__.py       # Agents package initializer
├── core/
│   ├── batch_manager.py  # Multi-FRD batch job manager & SSE streaming
│   ├── frd_worker.py     # Worker thread for single-FRD test generation
│   ├── cs_agent.py       # Core test script generator (Cucumber & Selenium)
│   ├── llm_factory.py    # Multi-model LLM factory with rate-limiting & fallbacks
│   ├── constants.py      # Centralized paths, configs, regexes, and system defaults
│   ├── checkpoint.py     # Resilient state checkpointing for long runs
│   ├── models.py         # Structured Python dataclasses (DTOs) & Pydantic schemas
│   └── __init__.py       # Core package initializer
├── input_modules/        # FRD and Manual Test Case modules (.docx)
├── src/                  # React UI frontend (Vite + React 19)
│   ├── components/       # UI Components (Jira ingestion, metrics cards, tracker)
│   ├── App.jsx           # Main application state and flow coordinator
│   └── index.css         # Styling system & responsive layout
├── server.py             # Unified FastAPI backend orchestrator & REST API
├── calculate_totals.py   # Utility script to calculate test suite metrics
├── run_pipeline.py       # Headless CLI batch execution script
├── package.json          # Node dependencies & frontend scripts
├── requirements.txt      # Consolidated Python dependencies
└── vite.config.js        # Vite configuration with API reverse proxy
```

---

## ⚙️ Quick Start

### Prerequisites
* **Python 3.10+**
* **Node.js 18+**
* **Gemini API Key** (Set as `GEMINI_API_KEY` in `.env` or input via the UI modal)

### Setup Instructions

1. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Frontend Dependencies:**
   ```bash
   npm install
   ```

3. **Configure Environment Variables (Optional):**
   Create a `.env` file in the project root to pre-configure credentials:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   SERVER_PORT=8000
   SERVER_HOST=127.0.0.1
   JIRA_URL=https://your-domain.atlassian.net
   JIRA_EMAIL=your-email@domain.com
   JIRA_API_TOKEN=your_jira_api_token
   ```

### Running the Application

To run the application locally, start the backend and frontend:

* **Start the FastAPI Backend:**
  ```bash
  npm run server
  # Or: python server.py
  ```
  The API will run on `http://127.0.0.1:8000`.

* **Start the React Frontend:**
  ```bash
  npm run dev
  ```
  Open `http://localhost:5173` in your browser.

---

## 🔌 API Endpoints

### Jira Integration
* **`GET /api/jira/epic/{issue_key}`** — Fetches an Epic and returns categorized attachments.
* **`POST /api/jira/evaluate`** — Classifies and downloads Epic attachments into `input_modules/`.

### Pipeline Execution
* **`POST /api/stage1-parse`** — Ingests and parses FRD & Test Case `.docx` files into structured JSON.
* **`POST /api/stage2-generate`** — Triggers LLM agents to generate Cucumber & Selenium test suites.
* **`GET /api/download-zip`** — Packs generated test artifacts into a ZIP stream for download.

### Batch Execution (Parallel Multi-FRD)
* **`POST /api/batch/submit`** — Submits a batch of FRDs for parallel generation.
* **`GET /api/batch/{job_id}/stream`** — Server-Sent Events (SSE) live progress stream.
* **`GET /api/batch/{job_id}/download`** — Downloads all generated tests for a batch job.
