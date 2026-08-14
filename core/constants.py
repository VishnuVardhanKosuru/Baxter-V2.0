"""
core/constants.py
-----------------
Centralised, side-effect-free configuration for the Baxter Test Automation
Intelligence Platform.

This module ONLY defines values. It never calls load_dotenv() (the application
entry-point server.py does that) and it never creates directories (side-effects
belong in the code that writes files, not in a config module).

Sections
--------
  1. Workspace & Directory Paths
  2. Agent & LLM Configuration
  3. Server Configuration
  4. Regex Patterns
  5. FRD Parsing Constants
  6. Test-Case Parsing Constants
  7. File Classification Keywords
  8. System Defaults
"""

import os
import re
from pathlib import Path


# -- 1. WORKSPACE & CANONICAL DIRECTORY PATHS ----------------------------------
# Single source of truth for every filesystem path used across Baxter.
# Directories are NOT created here -- each module creates what it needs
# exactly when it writes files (lazy creation).

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()

DIR_CORE   = WORKSPACE_ROOT / "core"
DIR_AGENTS = WORKSPACE_ROOT / "agents"

# Output hierarchy:
#   output/
#     knowledge/   <- parsed JSON artefacts (one per module)
#     jobs/        <- batch job working directories
DIR_OUTPUT    = WORKSPACE_ROOT / "output"
DIR_KNOWLEDGE = DIR_OUTPUT / "knowledge"   # JSON files live here
DIR_JOBS      = DIR_OUTPUT / "jobs"        # batch job dirs live here

DIR_MODULES_INPUT = WORKSPACE_ROOT / "input_modules"
SUPPORTED_DOC_EXT = ".docx"

# Standard file names
NAME_EXPECTED_CSV           = "expected.csv"
DEFAULT_OUTPUT_FILENAME     = "parsed_output.json"
DEFAULT_SAMPLE_FRD_FILENAME = "ShopSphere_Functional_Requirements_Document.docx"
DEFAULT_SAMPLE_TC_FILENAME  = "ShopSphere_Manual_Testcases.docx"

FILE_EXPECTED_CSV   = DIR_KNOWLEDGE / NAME_EXPECTED_CSV
DEFAULT_INPUT_PATH  = str(DIR_KNOWLEDGE / DEFAULT_OUTPUT_FILENAME)
DEFAULT_OUTPUT_PATH = str(DIR_KNOWLEDGE)


# -- 2. AGENT & LLM CONFIGURATION ---------------------------------------------
# Model list in preference order. FALLBACK_MODEL is determined by index so
# any future model renaming does not silently break the fallback logic.

AVAILABLE_MODELS: list = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

DEFAULT_MODEL: str = os.environ.get("GEMINI_MODEL", AVAILABLE_MODELS[0])

_default_idx   = AVAILABLE_MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in AVAILABLE_MODELS else 0
FALLBACK_MODEL: str = (
    AVAILABLE_MODELS[_default_idx + 1]
    if _default_idx + 1 < len(AVAILABLE_MODELS)
    else AVAILABLE_MODELS[-1]
)

DEFAULT_BASE_URL:       str = os.environ.get("BASE_URL", "https://shop.shopsphere.com")
MAX_LLM_RETRIES:        int = 3
RATE_LIMIT_BASE_WAIT_S: int = 5
NETWORK_BASE_WAIT_S:    int = 3
LLM_TEMPERATURE:      float = 0.2
SEPARATOR_WIDTH:        int = 62


# -- 3. SERVER CONFIGURATION --------------------------------------------------
# All values overridable via environment variables.
# ALLOWED_ORIGINS: comma-separated; default "*" for local dev only.
# PRODUCTION: set ALLOWED_ORIGINS=https://your-app.com in .env

SERVER_HOST: str = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT: int = int(os.environ.get("SERVER_PORT", "5000"))

ALLOWED_ORIGINS: list = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
]


# -- 4. REGEX PATTERNS --------------------------------------------------------
# Pre-compiled at module load time to avoid repeated re.compile() calls
# inside tight loops (e.g. the FRD parser iterates hundreds of paragraphs).

REGEX_WHITESPACE      = re.compile(r"\s+")
REGEX_NUMBERED_STEPS  = re.compile(r"(?<!\d)\d+\.\s+")
REGEX_DELIMITER_SPLIT = re.compile(r"[;\n]")
REGEX_TYPE_SPLIT      = re.compile(r"[/,]")
REGEX_REQUIREMENT_ID  = re.compile(r"(FR-\d+)\s*[-\u2013\u2014]+\s*(.+)")
REGEX_TC_ID           = re.compile(r"(TC-\d+)", re.IGNORECASE)
REGEX_TC_TITLE        = re.compile(r"TC-\d+[:\s\-\u2013\u2014]+(.+)", re.IGNORECASE)
REGEX_NON_ALPHANUM    = re.compile(r"\W+")


# -- 5. FRD PARSING CONSTANTS -------------------------------------------------
# Keywords used to identify paragraph headings and table row labels in FRDs.
# All matching is performed on lowercased, stripped text.

HEADING_REQUIREMENT_KEYWORD = "Requirement ID:"
XML_PARAGRAPH_TAG           = "p"
XML_TABLE_TAG               = "tbl"
XML_TEXT_TAG_SUFFIX         = "}t"

KEY_DESCRIPTION    = "description"
KEY_ACTORS         = "actor"
KEY_PRECONDITIONS  = ("pre-condition", "precondition")
KEY_TRIGGER        = "trigger"
KEY_MAIN_FLOW      = "main flow"
KEY_EXCEPTION_FLOW = ("alternate", "exception")
KEY_POSTCONDITIONS = ("post-condition", "postcondition")
KEY_BUSINESS_RULES = "business rule"
KEY_PRIORITY       = "priority"


# -- 6. TEST-CASE PARSING CONSTANTS -------------------------------------------
# Column-header matching signals for the Manual Test Cases .docx table.
# Tuples allow alternative header spellings for the same logical column.

COL_TEST_NAME        = ("test name", "name")
COL_TYPE             = "type"
COL_SUBJECT          = "subject"
COL_DESCRIPTION      = "description"
COL_EXPECTED_RESULT  = ("expected result", "expected")
COL_EXECUTION_STATUS = ("execution status", "status")


# -- 7. FILE CLASSIFICATION KEYWORDS ------------------------------------------
# Used by ModuleFolderScanner to classify files inside each module folder.

FRD_FILENAME_KEYWORDS = ["frd", "requirement", "spec", "functional"]
TC_FILENAME_KEYWORDS  = ["tc", "test", "manual", "case", "mtc"]


# -- 8. SYSTEM DEFAULTS -------------------------------------------------------

UNKNOWN_FEATURE_REF  = "UNKNOWN"
DEFAULT_PROJECT_NAME = "ShopSphere"
DEFAULT_VERSION      = "2.0"
