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
│   └── doc_parser.py     # Stage 1: Document Parsing & Enrichment Engine
├── src/
│   ├── components/       # App UI components (Ingestion, PipelineTracker, Metrics)
│   ├── App.jsx           # Main React controller
│   └── index.css         # Styling system
├── c&s_agent.py          # Stage 2: Unified BDD & Selenium Code Generator Agent
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
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### Running the Application

To run the application locally, you can start the backend and frontend concurrently:

* **Start the FastAPI Backend:**
  ```bash
  python server.py
  ```
  The API will be available on [http://127.0.0.1:5000](http://127.0.0.1:5000).

* **Start the React Frontend:**
  ```bash
  npm run dev
  ```
  Open the URL shown in the terminal (usually [http://localhost:5173](http://localhost:5173)) in your browser.

---

## 💻 CLI Usage

You can also run both stages of the parsing and generation pipeline via the command line.

### Stage 1: Parse and Enrich Documents
```bash
python agents/doc_parser.py \
  --frd  "ShopSphere_Functional_Requirements_Document.docx" \
  --tc   "ShopSphere_Manual_Testcases.docx" \
  --out  "output"
```

### Stage 2: Generate Cucumber & Selenium Tests
```bash
python c&s_agent.py \
  --input "output/shopsphere_parsed.json" \
  --out   "output/tests" \
  --model "gemini-2.5-flash"
```

---

## 🔌 API Endpoints

* **`GET /api/health`** — Service health status check.
* **`POST /api/parse`** — Ingests the FRD & Test Case `.docx` files, processes both stages, and saves the output in `output/`.
* **`GET /api/download-zip`** — Packs the generated cucumber and selenium files inside `output/tests/` into an in-memory ZIP archive stream.
