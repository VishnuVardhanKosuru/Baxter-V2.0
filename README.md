# Baxter: Requirement & Test Case Automation Engine

Baxter is an automated pipeline that parses Functional Requirements Documents (FRD) and Manual Test Cases, maps them using fuzzy matching algorithms, and leverages LLM agents to generate BDD Cucumber scenarios, Selenium pytest scripts, and CSV execution step matrices.

The project features a **FastAPI backend** that interfaces with Python parsing agents and a modern **React + Vite frontend** with progress metrics trackers.

---

## 🚀 Key Features

* **Dual-Document Parsing:** Automatically extracts and links structured requirements from FRDs and manual test documents (`.docx`).
* **Fuzzy Subject-to-Feature Mapping:** Integrates a 3-tier matching engine (substring matching, word overlap, and Levenshtein distance) to dynamically bind tests to requirements.
* **Unified Agent Code Generation:** Utilizes a Pydantic-structured prompt chain to generate Cucumber (`.feature`), Selenium (`pytest` / `.py`), and CSV steps in a single, aligned, cost-effective LLM call.
* **Fallback Template Engine:** Operates in offline mode generating standardized template scenarios if Gemini API credentials are not provided.
* **Web UI Dashboard:** Clean React interface tracking real-time pipeline status, stopwatch timings, test case metrics, and an in-memory ZIP package download utility.

---

## 🛠️ Project Structure

```text
Baxter/
├── agents/
│   ├── constants.py      # Pre-compiled regex, table keys, and system constants
│   ├── models.py         # Structured Python dataclasses (DTOs)
│   ├── doc_parser.py     # Stage 1: Document Parsing & Enrichment Engine
│   └── cs_agent.py       # Stage 2: Unified BDD & Selenium Code Generator Agent
├── samples/              # Default `.docx` fallback sample documents
├── src/
│   ├── components/       # App UI components
│   ├── App.jsx           # Main React controller
│   └── index.css         # Styling system
├── server.py             # FastAPI backend orchestrating python processes
├── vite.config.js        # React/Vite development server configurations
└── package.json          # Node dependencies & package scripts
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
