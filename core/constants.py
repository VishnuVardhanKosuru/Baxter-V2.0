"""
core/constants.py
─────────────────
Centralized configuration, directory paths, regex patterns, field mappings,
and platform defaults for the Baxter Test Automation Intelligence Platform.
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── WORKSPACE & CANONICAL DIRECTORY PATHS ────────────────────────────────────
# Single source of truth for all filesystem directories across Baxter.

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
DIR_CORE       = WORKSPACE_ROOT / "core"
DIR_AGENTS     = WORKSPACE_ROOT / "agents"
DIR_SAMPLES    = WORKSPACE_ROOT / "samples"
DIR_UPLOADS    = WORKSPACE_ROOT / "uploads"
DIR_OUTPUT     = WORKSPACE_ROOT / "output"
DIR_TESTS      = DIR_OUTPUT / "tests"
DIR_CUCUMBER   = DIR_TESTS / "cucumber"
DIR_SELENIUM   = DIR_TESTS / "selenium"

# Standard Directory Names
NAME_CORE_DIR      = "core"
NAME_AGENTS_DIR    = "agents"
NAME_OUTPUT_DIR    = "output"
NAME_TESTS_DIR     = "tests"
NAME_CUCUMBER_DIR  = "cucumber"
NAME_SELENIUM_DIR  = "selenium"
NAME_UPLOADS_DIR   = "uploads"
NAME_SAMPLES_DIR   = "samples"

# Standard File Names
NAME_EXPECTED_CSV            = "expected.csv"
DEFAULT_OUTPUT_FILENAME      = "parsed_output.json"
DEFAULT_SAMPLE_FRD_FILENAME  = "ShopSphere_Functional_Requirements_Document.docx"
DEFAULT_SAMPLE_TC_FILENAME   = "ShopSphere_Manual_Testcases.docx"

FILE_EXPECTED_CSV = DIR_TESTS / NAME_EXPECTED_CSV
DEFAULT_INPUT_PATH  = str(DIR_OUTPUT / DEFAULT_OUTPUT_FILENAME)
DEFAULT_OUTPUT_PATH = str(DIR_TESTS)

# Ensure runtime directories exist
for _directory in (DIR_OUTPUT, DIR_TESTS, DIR_CUCUMBER, DIR_SELENIUM, DIR_UPLOADS, DIR_SAMPLES):
    _directory.mkdir(parents=True, exist_ok=True)


# ─── AGENT & LLM CONFIGURATION CONSTANTS ──────────────────────────────────────
# High-quota Gemini models: 500 RPD, 15 RPM
DEFAULT_MODEL:          str = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODEL:         str = "gemini-3.1-flash-lite" if "3.5" in DEFAULT_MODEL else "gemini-3.5-flash-lite"
AVAILABLE_MODELS:  list[str] = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

DEFAULT_BASE_URL:       str = os.environ.get("BASE_URL", "https://shop.shopsphere.com")
MAX_LLM_RETRIES:        int = 3
RATE_LIMIT_BASE_WAIT_S: int = 5
NETWORK_BASE_WAIT_S:    int = 3
LLM_TEMPERATURE:      float = 0.2
SEPARATOR_WIDTH:        int = 62


# ─── SERVER CONFIGURATION ─────────────────────────────────────────────────────
SERVER_HOST:            str = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT:            int = int(os.environ.get("SERVER_PORT", "5000"))


# ─── REGEX PATTERNS ───────────────────────────────────────────────────────────
REGEX_WHITESPACE       = re.compile(r"\s+")
REGEX_NUMBERED_STEPS   = re.compile(r"(?<!\d)\d+\.\s+")
REGEX_DELIMITER_SPLIT  = re.compile(r"[;\n]")
REGEX_TYPE_SPLIT       = re.compile(r"[/,]")
REGEX_REQUIREMENT_ID   = re.compile(r"(FR-\d+)\s*[—–\-]+\s*(.+)")
REGEX_TC_ID            = re.compile(r"(TC-\d+)", re.IGNORECASE)
REGEX_TC_TITLE         = re.compile(r"TC-\d+[:\s—–\-]+(.+)", re.IGNORECASE)
REGEX_NON_ALPHANUM     = re.compile(r"\W+")


# ─── FRD PARSING CONSTANTS ───────────────────────────────────────────────────
HEADING_REQUIREMENT_KEYWORD = "Requirement ID:"
XML_PARAGRAPH_TAG           = "p"
XML_TABLE_TAG               = "tbl"
XML_TEXT_TAG_SUFFIX         = "}t"

# FRD Table Keys Matching Signals
KEY_DESCRIPTION    = "description"
KEY_ACTORS         = "actor"
KEY_PRECONDITIONS  = ("pre-condition", "precondition")
KEY_TRIGGER        = "trigger"
KEY_MAIN_FLOW      = "main flow"
KEY_EXCEPTION_FLOW = ("alternate", "exception")
KEY_POSTCONDITIONS = ("post-condition", "postcondition")
KEY_BUSINESS_RULES = "business rule"
KEY_PRIORITY       = "priority"


# ─── TEST CASE PARSING CONSTANTS ──────────────────────────────────────────────
COL_TEST_NAME        = ("test name", "name")
COL_TYPE             = "type"
COL_SUBJECT          = "subject"
COL_DESCRIPTION      = "description"
COL_EXPECTED_RESULT  = ("expected result", "expected")
COL_EXECUTION_STATUS = ("execution status", "status")


# ─── SYSTEM DEFAULTS ─────────────────────────────────────────────────────────
UNKNOWN_FEATURE_REF  = "UNKNOWN"
DEFAULT_PROJECT_NAME = "ShopSphere"
DEFAULT_VERSION      = "2.0"
