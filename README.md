# Baxter: Requirement & Test Case Automation Engine

Baxter is an automated pipeline that parses Functional Requirements Documents (FRD) and Manual Test Cases, maps them using fuzzy matching algorithms, and leverages LLM agents to generate BDD Cucumber scenarios, Selenium pytest scripts, and CSV execution step matrices.

The project features a **FastAPI backend** that interfaces with Python parsing agents and a modern **React + Vite frontend** with progress metrics trackers.

---

## 🚀 Key Features

* **Dual-Document Parsing:** Automatically extracts and links structured requirements from FRDs and manual test documents (`.docx`).
* **Fuzzy Subject-to-Feature Mapping:** Integrates a 3-tier matching engine (substring matching, word overlap, and Levenshtein distance) to dynamically bind tests to requirements.
* **Unified Single-Chain Code Generation:** Utilizes a Pydantic-structured prompt chain to generate Cucumber (`.feature`), Selenium (`pytest` / `.py`), and CSV steps in a single, aligned, cost-effective LLM call.
* **High-Quota Gemini Intelligence:** Powered by **Google Gemini 3.5 Flash Lite** (500 RPD / 15 RPM) with automatic rate-limit backoff resilience.
* **Web UI Dashboard:** Clean React interface tracking real-time pipeline status, stopwatch timings, test case metrics, and an in-memory ZIP package download utility.

---

## 📖 In-Depth Documentation

Detailed technical and operational documentation is available in the [`Documentation/`](file:///c:/Users/2862390/Desktop/New%20folder%20(3)/Baxter/Documentation/) directory:
* **[Parser Agent Documentation](file:///c:/Users/2862390/Desktop/New%20folder%20(3)/Baxter/Documentation/PARSER_AGENT_DOCUMENTATION.md)**: Deep dive into AST extraction, `python-docx` rationale, fuzzy matching, and context enrichment.
* **[Tester Agent Documentation](file:///c:/Users/2862390/Desktop/New%20folder%20(3)/Baxter/Documentation/TESTER_AGENT_DOCUMENTATION.md)**: Deep dive into the unified LangChain prompt chain, Gemini 3.5 Flash Lite integration, Pydantic schemas, and output artifact specifications.

---

## 🛠️ Project Structure

```text
Baxter/
├── core/
│   ├── constants.py      # Centralized paths, configs, regexes, and system defaults
│   ├── models.py         # Structured Python dataclasses (DTOs) & Pydantic schemas
│   └── __init__.py       # Core package initializer
├── agents/
│   ├── doc_parser.py     # Stage 1: Document Parsing & Context Enrichment Agent
│   ├── cs_agent.py       # Stage 2: Unified BDD & Selenium Code Generator Agent
│   └── __init__.py       # Agents package initializer
├── samples/              # Default `.docx` fallback sample documents
├── src/                  # React UI frontend (Vite + React 19)
├── server.py             # FastAPI backend orchestrator & REST API
├── package.json          # Node dependencies & frontend scripts
└── requirements.txt      # Python dependencies
```

---

## ⚙️ Quick Start

### Prerequisites
* **Python 3.10+**
* **Node.js 18+**
* **Gemini API Key** (Set as `GEMINI_API_KEY` or `GOOGLE_API_KEY` in a `.env` file)

### Setup Instructions

1. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Frontend Dependencies:**
   ```bash
   npm install
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the project root to control server settings and LLM keys:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.1-flash-lite
   SERVER_PORT=5000
   SERVER_HOST=127.0.0.1
   ```

### Running the Application

To run the application locally, start the backend and frontend in separate terminals:

* **Start the FastAPI Backend:**
  ```bash
  npm run server
  # Or natively: python server.py
  ```
  The API will be available on [http://127.0.0.1:5000](http://127.0.0.1:5000). Logs are printed cleanly to this terminal.

* **Start the React Frontend:**
  ```bash
  npm run dev
  ```
  Open the URL shown in the terminal (usually [http://localhost:5173](http://localhost:5173)) in your browser.

---

## 🔌 API Endpoints

The system relies strictly on HTTP API endpoints; the internal CLI has been deprecated to guarantee clean execution boundaries.

* **`GET /api/health`** — Service health status check.
* **`POST /api/stage1-parse`** — Ingests the FRD & Test Case `.docx` files, processes them, and saves the output JSON in `output/`.
* **`POST /api/stage2-generate`** — Triggers the LLM agents to generate cucumber and selenium test suites inside `output/tests/`.
* **`GET /api/download-zip`** — Packs the generated cucumber and selenium files into an in-memory ZIP archive stream for browser download.
