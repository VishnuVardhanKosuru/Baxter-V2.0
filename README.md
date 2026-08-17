# Baxter — Requirement & Test Case Automation Engine

Baxter is an automated pipeline that parses Functional Requirements Documents (FRD) and
manual test case documents, maps test cases to requirements, and uses LLM agents to
generate BDD Cucumber scenarios, Selenium pytest scripts, and CSV execution step matrices.

A **FastAPI** backend drives the Python parsing and generation agents; a **React + Vite**
frontend provides the dashboard, live progress tracking, and cost telemetry.

---

## Key Features

* **Dual-document parsing** — extracts structured requirements from FRDs and test cases
  from `.docx` files, and links them together.
* **LLM requirement mapping with heuristic fallback** — one batched LLM call maps every
  test case in a module to its FRD sections. If no API key is configured or the call
  fails, a keyword-overlap mapper takes over so parsing always produces output.
* **Unified single-call generation** — a Pydantic-structured prompt chain produces the
  Cucumber `.feature`, the Selenium `pytest` script, and the CSV steps in one LLM call,
  so all three artifacts share a single context window and stay aligned.
* **Multi-provider, multi-key routing** — Gemini, OpenAI, and Anthropic are auto-detected
  from the model name. Up to 9 keys per provider are load-balanced by LiteLLM with
  automatic retry, timeout, and least-busy routing.
* **Prompt caching** — Gemini explicit context cache, OpenAI automatic prefix caching, and
  Anthropic `cache_control` are each applied per provider.
* **Cost & token telemetry** — every LLM call is logged with its token counts and cost,
  aggregated per pipeline phase and per API key, and downloadable as an audit report.
* **Batch mode with live progress** — submit N FRD+TC pairs and stream per-FRD progress
  over Server-Sent Events, with crash-recovery checkpoints.
* **Jira ingestion** — pull FRD and test case attachments straight from a Jira Epic
  (including its child issues) into `input_modules/`.

---

## Project Structure

Modules live in `agents/` if they own or execute an LLM prompt, and in `core/` if
they are shared infrastructure.

```text
Baxter/
├── agents/                 # Pipeline stages (own or execute a prompt)
│   ├── doc_parser.py       # Stage 1: .docx extraction + mapping + enrichment
│   ├── cs_agent.py         # Stage 2: Cucumber + Selenium generator
│   ├── frd_worker.py       # Stage 2 parallel executor (abatch per FRD)
│   ├── jira_agent.py       # Jira REST client + attachment classifier
│   └── jira_prompts.py     # Jira classifier system prompt
├── core/                   # Shared infrastructure (no prompts)
│   ├── constants.py        # ALL configuration, paths, regexes, env helpers
│   ├── models.py           # Dataclass DTOs + Pydantic LLM output schemas
│   ├── llm_factory.py      # Multi-provider LLM router, caching, cost callback
│   ├── batch_manager.py    # Batch job state + orchestration
│   ├── checkpoint.py       # Crash-recovery checkpoints
│   ├── cost_report.py      # Shared cost log parsing & reporting
│   └── logger.py           # Central logging configuration
├── src/                    # React UI (Vite + React 19)
├── samples/                # Optional demo .docx documents (see samples/README.md)
├── input_modules/          # Input documents, one folder per module (gitignored)
├── output/                 # Generated artifacts (gitignored)
│   ├── knowledge/          #   parsed JSON, one per module
│   ├── tests/              #   generated artifacts, one folder per module
│   └── jobs/               #   batch job working directories
├── server.py               # FastAPI backend & REST API
├── run_pipeline.py         # CLI: full pipeline without the server
├── calculate_totals.py     # CLI: aggregate cost totals
└── requirements.txt        # Python runtime dependencies (pinned)
```

`agents/doc_parser.py` spans two layers in one module, ordered extraction-first
and separated by labelled section banners:

| Sections | Layer | Contents |
| --- | --- | --- |
| 1–3 | Deterministic extraction (no LLM, no network) | text utilities, folder discovery, FRD AST, test case tables |
| 4–6 | LLM orchestration | requirement mapping, enrichment, `parse_documents` |

---

## Quick Start

### Prerequisites

* Python 3.10+
* Node.js 18+
* An API key for at least one LLM provider (Gemini, OpenAI, or Anthropic)

### Setup

1. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install frontend dependencies**
   ```bash
   npm install
   ```

3. **Configure environment**

   Copy the template and fill in at least one API key. Every available setting is
   documented inline in [`.env.example`](.env.example).
   ```bash
   cp .env.example .env
   ```

   Minimum viable `.env`:
   ```env
   GEMINI_API_KEY=your_key_here
   ```

   A key can also be supplied at runtime through the UI credentials dialog, in which
   case it is registered as an additional routed deployment for that server process.

### Running

Start the backend and frontend in separate terminals.

* **Backend** — serves on `http://127.0.0.1:8000` by default:
  ```bash
  npm run server
  ```

* **Frontend** — opens on `http://localhost:5173` and proxies `/api` to the backend:
  ```bash
  npm run dev
  ```

### Running without the server

```bash
python run_pipeline.py
```

Parses everything in `input_modules/`, generates artifacts into `output/tests/`, and
writes cost totals to `output/cost_totals.txt`. Exit code `0` on success, `1` if parsing
produced nothing, `2` if every module failed generation.

---

## Input Document Format

Place one folder per module inside `input_modules/`. Each folder needs an FRD document and
a test case document; they are told apart by filename keywords (`frd`, `requirement`,
`spec`, `functional` vs `tc`, `test`, `manual`, `case`, `mtc`).

```text
input_modules/
└── 01_User_Auth/
    ├── FRD_UserAuth.docx
    └── TC_UserAuth.docx
```

**FRD** — Word `Heading` styles delimit sections. A heading containing `Requirement ID:`
starts a functional requirement, and the adjacent two-column table supplies its metadata
(`Description`, `Actors`, `Trigger`, `Priority`, `Pre-Conditions`, `Main Flow`,
`Post-Conditions`, `Business Rules`, `Exception Flows`).

**Test cases** — one or more tables with a header row. A `Test Name` column is required;
`Type`, `Subject`, `Description`, `Expected Result`, and `Execution Status` are used when
present. Test IDs are read from the `TC-nnn` pattern in the test name.

---

## API Endpoints

### Health
| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness plus a non-sensitive config snapshot (never returns key material) |

### Sequential pipeline
| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/stage1-parse` | Parse FRD + TC documents into `output/knowledge/` |
| `POST` | `/api/stage2-generate` | Generate artifacts into `output/tests/<module>/` |
| `GET`  | `/api/download-zip` | Stream all generated tests as a ZIP |

`stage1-parse` resolves its input in this order: `input_modules/`, then the bundled
samples, then the uploaded file pair. If samples are requested but absent, it falls back
to `input_modules/` rather than failing.

### Batch pipeline
| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/batch/submit` | Upload N FRD+TC pairs; returns a `job_id` immediately |
| `GET`  | `/api/batch/{job_id}/stream` | SSE live progress stream |
| `GET`  | `/api/batch/{job_id}/status` | JSON snapshot of job state |
| `GET`  | `/api/batch/{job_id}/download` | ZIP the whole job |
| `GET`  | `/api/batch/{job_id}/download/{frd_id}` | ZIP one FRD's output |

### Jira ingestion
| Method | Path | Description |
| --- | --- | --- |
| `GET`  | `/api/jira/epics` | List accessible Epics |
| `GET`  | `/api/jira/epic/{issue_key}` | Classify one Epic's attachments |
| `POST` | `/api/jira/evaluate` | Download attachments into numbered `input_modules/` folders |

Credentials come from `X-Jira-Url`, `X-Jira-Email`, and `X-Jira-Token` headers, falling
back to the corresponding `.env` values.

### Cost tracking
| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/cost/metrics` | Aggregated token and cost metrics |
| `GET` | `/api/cost/download-report` | Cost audit report as `.txt` |

---

## Production Notes

* **CORS** — `ALLOWED_ORIGINS` defaults to `*` for local development, which also disables
  credentialed CORS. Set an explicit origin list before deploying.
* **Error detail** — internal exception text is returned to clients only when
  `DEBUG_ERRORS=true`. Otherwise clients get a generic message plus an `X-Request-ID`
  that correlates to the full server-side traceback.
* **Auto-reload** — off unless `SERVER_RELOAD=true`. Never enable it in production.
* **Uploads** — restricted to `.docx` and capped by `MAX_UPLOAD_MB`; filenames are
  sanitized to a bare basename before being written.
* **Job state** — batch jobs live in an in-process dictionary, so a multi-worker
  deployment needs a shared store (e.g. Redis) before scaling beyond one worker.
* **Logging** — set `LOG_LEVEL` and, optionally, `LOG_TO_FILE=true` to write rotating
  logs to `logs/baxter.log`.

---

