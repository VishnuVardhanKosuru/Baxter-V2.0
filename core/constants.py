"""
core/constants.py
-----------------
Centralised, side-effect-free configuration for the Baxter Test Automation
Intelligence Platform.

This module ONLY defines values. It never calls load_dotenv() (the application
entry-points server.py / run_pipeline.py do that) and it never creates
directories (side-effects belong in the code that writes files).

Sections
--------
  1. Environment helpers
  2. Workspace & Directory Paths
  3. Agent & LLM Configuration
  4. Server Configuration
  5. Logging Configuration
  6. Jira Configuration
  7. Regex Patterns
  8. FRD Parsing Constants
  9. Test-Case Parsing Constants
 10. File Classification Keywords
 11. System Defaults
"""

import os
import re
from pathlib import Path


# -- 1. ENVIRONMENT HELPERS ----------------------------------------------------
# Typed getters that never raise on malformed input. A bad env value falls back
# to the documented default instead of crashing the process at import time.

def env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to `default` if unset or malformed."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    """Read a float env var, falling back to `default` if unset or malformed."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean env var. Truthy: 1, true, yes, on (case-insensitive)."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# -- 2. WORKSPACE & CANONICAL DIRECTORY PATHS ----------------------------------
# Single source of truth for every filesystem path used across Baxter.
# Directories are NOT created here -- each module creates what it needs
# exactly when it writes files (lazy creation).

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()

# Output hierarchy:
#   output/
#     knowledge/   <- parsed JSON artefacts (one per module)
#     jobs/        <- batch job working directories
#     tests/       <- generated artefacts, one sub-dir per module
DIR_OUTPUT    = WORKSPACE_ROOT / "output"
DIR_KNOWLEDGE = DIR_OUTPUT / "knowledge"
DIR_JOBS      = DIR_OUTPUT / "jobs"
DIR_TESTS     = DIR_OUTPUT / "tests"

DIR_UPLOADS       = WORKSPACE_ROOT / "uploads"
DIR_MODULES_INPUT = WORKSPACE_ROOT / "input_modules"
DIR_SAMPLES       = WORKSPACE_ROOT / "samples"
DIR_LOGS          = WORKSPACE_ROOT / "logs"

# Cost tracking artefacts (single definition -- consumed by llm_factory,
# server.py and the cost report module alike).
FILE_COST_LOG    = DIR_OUTPUT / "cost_tracking.txt"
FILE_COST_TOTALS = DIR_OUTPUT / "cost_totals.txt"

# Standard file names
NAME_EXPECTED_CSV       = "expected.csv"
NAME_CHECKPOINT         = "checkpoint.json"
DEFAULT_OUTPUT_FILENAME = "parsed_output.json"

# Bundled sample documents, resolved inside DIR_SAMPLES.
SAMPLE_FRD_FILENAME = os.environ.get(
    "SAMPLE_FRD", "ShopSphere_Functional_Requirements_Document.docx"
)
SAMPLE_TC_FILENAME = os.environ.get(
    "SAMPLE_TC", "ShopSphere_Manual_Testcases.docx"
)

DEFAULT_INPUT_PATH  = str(DIR_KNOWLEDGE / DEFAULT_OUTPUT_FILENAME)
DEFAULT_OUTPUT_PATH = str(DIR_KNOWLEDGE)

# CSV header for the generated step matrix. Defined once so agents/cs_agent.py
# and agents/frd_worker.py can never drift out of sync.
CSV_HEADERS = [
    "testcase", "description", "category", "preconditions",
    "stepname", "expected result", "testdata", "evidence required",
]


# -- 3. AGENT & LLM CONFIGURATION ---------------------------------------------

AVAILABLE_MODELS: list = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
]

DEFAULT_MODEL: str = os.environ.get("LLM_MODEL", os.environ.get("GEMINI_MODEL", AVAILABLE_MODELS[0]))

# Retry / backoff behaviour for direct (non-router) LLM invocation.
MAX_LLM_RETRIES:        int = env_int("LLM_MAX_RETRIES", 5)
RATE_LIMIT_BASE_WAIT_S: int = env_int("RATE_LIMIT_BASE_WAIT_S", 30)
NETWORK_BASE_WAIT_S:    int = env_int("NETWORK_BASE_WAIT_S", 3)

# LiteLLM Router tuning.
LLM_TIMEOUT_S:        int = env_int("LLM_TIMEOUT_S", 120)
LLM_ROUTER_RETRIES:   int = env_int("LLM_ROUTER_RETRIES", 5)
LLM_RETRY_AFTER_S:    int = env_int("LLM_RETRY_AFTER_S", 5)
LLM_COOLDOWN_S:       int = env_int("LLM_COOLDOWN_S", 5)
LLM_ALLOWED_FAILS:    int = env_int("LLM_ALLOWED_FAILS", 10)
LLM_TEMPERATURE:    float = env_float("LLM_TEMPERATURE", 0.2)
LLM_MAX_CONCURRENCY:  int = env_int("LLM_MAX_CONCURRENCY", 500)
LLM_CACHE_TTL_MINUTES: int = env_int("LLM_CACHE_TTL_MINUTES", 60)

# Highest key index probed when collecting PREFIX, PREFIX_2 ... PREFIX_N.
# Shared by _collect_keys(), the alias map, and the UI key injector so all
# three agree on how many key slots exist.
MAX_API_KEY_SLOTS: int = 9

# Provider -> (rpm env var, tpm env var, key prefix, default rpm, default tpm)
PROVIDER_ENV_MAP: dict = {
    "gemini":    ("GEMINI_RPM",    "GEMINI_TPM",    "GEMINI_API_KEY",    50,  4000000),
    "openai":    ("OPENAI_RPM",    "OPENAI_TPM",    "OPENAI_API_KEY",    500, 2000000),
    "anthropic": ("ANTHROPIC_RPM", "ANTHROPIC_TPM", "ANTHROPIC_API_KEY", 50,  2000000),
}

DEFAULT_BASE_URL: str = os.environ.get("BASE_URL", "https://shop.shopsphere.com")
SEPARATOR_WIDTH:  int = 62

# Truncation limits for the token-compact LLM mapping prompt.
COMPACT_SUMMARY_CHARS:  int = env_int("COMPACT_SUMMARY_CHARS", 140)
COMPACT_STEPS_CHARS:    int = env_int("COMPACT_STEPS_CHARS", 120)
COMPACT_INDEX_MAX_CHARS: int = env_int("COMPACT_INDEX_MAX_CHARS", 60000)

# Minimum word length considered significant by the heuristic fallback mapper.
FALLBACK_MIN_WORD_LEN: int = 3
FALLBACK_CONFIDENCE:   float = 0.85
FALLBACK_DEFAULT_CONFIDENCE: float = 0.70


# -- 4. SERVER CONFIGURATION --------------------------------------------------

SERVER_HOST:  str = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT:  int = env_int("SERVER_PORT", 8000)
SERVER_RELOAD: bool = env_bool("SERVER_RELOAD", False)

# Return raw exception text to HTTP clients. DEV ONLY -- leaks internals.
DEBUG_ERRORS: bool = env_bool("DEBUG_ERRORS", False)

MAX_UPLOAD_BYTES: int = env_int("MAX_UPLOAD_MB", 25) * 1024 * 1024

# CORS origins. "*" is dev-only; credentialed CORS is disabled when it is used
# because browsers reject `Access-Control-Allow-Origin: *` with credentials.
ALLOWED_ORIGINS: list = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
] or ["*"]

CORS_ALLOW_CREDENTIALS: bool = "*" not in ALLOWED_ORIGINS


# -- 5. LOGGING CONFIGURATION -------------------------------------------------

LOG_LEVEL:       str = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE:    bool = env_bool("LOG_TO_FILE", False)
LOG_FILE:       Path = DIR_LOGS / "baxter.log"
LOG_FORMAT:      str = "[%(asctime)s] [%(levelname)-7s] [%(module)-14s] %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


# -- 6. JIRA CONFIGURATION ----------------------------------------------------

JIRA_TIMEOUT_S:    int = env_int("JIRA_TIMEOUT_S", 30)
JIRA_MAX_RESULTS:  int = env_int("JIRA_MAX_RESULTS", 100)
JIRA_MAX_RETRIES:  int = env_int("JIRA_MAX_RETRIES", 3)
JIRA_BACKOFF_S:  float = env_float("JIRA_BACKOFF_S", 0.5)
JIRA_GEMINI_MODEL: str = os.environ.get("JIRA_GEMINI_MODEL", "gemini-flash-latest")
JIRA_OPENAI_MODEL: str = os.environ.get("JIRA_OPENAI_MODEL", "gpt-4o-mini")
JIRA_DOWNLOAD_CHUNK_BYTES: int = 8192

# Keyword sets for the rule-based Jira attachment classifier.
JIRA_FRD_KEYWORDS = ["frd", "req", "prd", "spec", "functional"]
JIRA_TC_KEYWORDS  = ["test", "tc", "scenario", "manual"]
JIRA_DOC_EXTENSIONS   = (".doc", ".docx", ".pdf")
JIRA_SHEET_EXTENSIONS = (".xlsx", ".xls", ".csv")


# -- 7. REGEX PATTERNS --------------------------------------------------------
# Pre-compiled at module load time to avoid repeated re.compile() calls
# inside tight loops (e.g. the FRD parser iterates hundreds of paragraphs).

REGEX_WHITESPACE      = re.compile(r"\s+")
REGEX_NUMBERED_STEPS  = re.compile(r"(?<!\d)\d+\.\s+")
REGEX_DELIMITER_SPLIT = re.compile(r"[;\n]")
REGEX_TYPE_SPLIT      = re.compile(r"[/,]")
REGEX_REQUIREMENT_ID  = re.compile(r"(FR-\d+)\s*[-–—]+\s*(.+)")
REGEX_TC_ID           = re.compile(r"(TC-\d+)", re.IGNORECASE)
REGEX_TC_TITLE        = re.compile(r"TC-\d+[:\s\-–—]+(.+)", re.IGNORECASE)
REGEX_LEADING_NUMBER  = re.compile(r"^[0-9.\s]+")
REGEX_NON_WORD        = re.compile(r"[^\w]+")

# Jira issue keys are PROJECT-123. Validated before interpolation into a REST
# path so a crafted key cannot traverse to another API endpoint.
REGEX_JIRA_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-\d+$")

# Cost log line format, written by core.llm_factory._track_cost_callback:
#   [timestamp] [Phase] Model: <name> (<key alias>) | Tokens: N In, M Out | Cost: $X
# The phase group is optional for backward compatibility with older logs.
REGEX_COST_LINE = re.compile(
    r"\[(.*?)\]\s+"
    r"(?:\[(.*?)\]\s+)?"
    r"Model:\s+(.*?)\s+\((.*?)\)\s+\|\s+"
    r"Tokens:\s+(\d+)\s+In,\s+(\d+)\s+Out\s+\|\s+"
    r"Cost:\s+\$([\d\.]+)"
)


# -- 8. FRD PARSING CONSTANTS -------------------------------------------------
# Keywords used to identify paragraph headings and table row labels in FRDs.
# All matching is performed on lowercased, stripped text.

HEADING_REQUIREMENT_KEYWORD = "Requirement ID:"
XML_PARAGRAPH_TAG           = "p"
XML_TABLE_TAG               = "tbl"
XML_TEXT_TAG_SUFFIX         = "}t"
XML_WORD_NAMESPACE          = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

KEY_DESCRIPTION    = "description"
KEY_ACTORS         = "actor"
KEY_PRECONDITIONS  = ("pre-condition", "precondition")
KEY_TRIGGER        = "trigger"
KEY_MAIN_FLOW      = "main flow"
KEY_EXCEPTION_FLOW = ("alternate", "exception")
KEY_POSTCONDITIONS = ("post-condition", "postcondition")
KEY_BUSINESS_RULES = "business rule"
KEY_PRIORITY       = "priority"

# Heading text -> (section id suffix, section type). Evaluated in order, so
# more specific keywords must precede more general ones.
SECTION_TYPE_RULES: tuple = (
    (("purpose",),                              "PURPOSE",  "general"),
    (("out of scope", "out-of-scope"),           "SCOPE",    "scope"),
    (("scope",),                                 "SCOPE",    "scope"),
    (("interface",),                             "INTF",     "interface"),
    (("performance",),                           "PERF",     "nfr"),
    (("non-functional", "nfr", "security"),      "NFR",      "nfr"),
    (("glossary",),                              "GLOSSARY", "glossary"),
)

SECTION_SLUG_MAX_LEN = 15
GLOSSARY_SKIP_TERMS  = ("term", "acronym")


# -- 9. TEST-CASE PARSING CONSTANTS -------------------------------------------
# Column-header matching signals for the Manual Test Cases .docx table.
# Tuples allow alternative header spellings for the same logical column.

COL_TEST_NAME        = ("test name", "name")
COL_TYPE             = ("type", "category")
COL_SUBJECT          = ("subject", "module")
COL_DESCRIPTION      = ("description",)
COL_EXPECTED_RESULT  = ("expected result", "expected")
COL_EXECUTION_STATUS = ("execution status", "status")

# A header target shorter than this must match a column heading exactly;
# longer targets may match as a substring. Prevents "tc" matching "structure".
COL_SUBSTRING_MIN_LEN = 3


# -- 10. FILE CLASSIFICATION KEYWORDS -----------------------------------------
# Used by ModuleFolderScanner to classify files inside each module folder.

SUPPORTED_DOC_EXT     = ".docx"
FRD_FILENAME_KEYWORDS = ["frd", "requirement", "spec", "functional"]
TC_FILENAME_KEYWORDS  = ["tc", "test", "manual", "case", "mtc"]
WORD_TEMP_PREFIX      = "~$"


# -- 11. SYSTEM DEFAULTS ------------------------------------------------------

UNKNOWN_FEATURE_REF  = "UNKNOWN"
DEFAULT_PROJECT_NAME = os.environ.get("DEFAULT_PROJECT_NAME", "ShopSphere")
DEFAULT_VERSION      = os.environ.get("DEFAULT_VERSION", "2.0")
