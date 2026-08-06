"""
constants.py
────────────
Centralized constants, regex patterns, field mappings, and configurations for document parsing.
"""

import re

# ─── REGEX PATTERNS ───────────────────────────────────────────────────────────
REGEX_WHITESPACE = re.compile(r"\s+")
REGEX_NUMBERED_STEPS = re.compile(r"(?<!\d)\d+\.\s+")
REGEX_DELIMITER_SPLIT = re.compile(r"[;\n]")
REGEX_TYPE_SPLIT = re.compile(r"[/,]")
REGEX_REQUIREMENT_ID = re.compile(r"(FR-\d+)\s*[—–\-]+\s*(.+)")
REGEX_TC_ID = re.compile(r"(TC-\d+)", re.IGNORECASE)
REGEX_TC_TITLE = re.compile(r"TC-\d+[:\s—–\-]+(.+)", re.IGNORECASE)
REGEX_NON_ALPHANUM = re.compile(r"\W+")

# ─── FRD PARSING CONSTANTS ───────────────────────────────────────────────────
HEADING_REQUIREMENT_KEYWORD = "Requirement ID:"
XML_PARAGRAPH_TAG = "p"
XML_TABLE_TAG = "tbl"
XML_TEXT_TAG_SUFFIX = "}t"

# FRD Table Keys Matching Signals
KEY_DESCRIPTION = "description"
KEY_ACTORS = "actor"
KEY_PRECONDITIONS = ("pre-condition", "precondition")
KEY_TRIGGER = "trigger"
KEY_MAIN_FLOW = "main flow"
KEY_EXCEPTION_FLOW = ("alternate", "exception")
KEY_POSTCONDITIONS = ("post-condition", "postcondition")
KEY_BUSINESS_RULES = "business rule"
KEY_PRIORITY = "priority"

# ─── TEST CASE PARSING CONSTANTS ──────────────────────────────────────────────
COL_TEST_NAME = ("test name", "name")
COL_TYPE = "type"
COL_SUBJECT = "subject"
COL_DESCRIPTION = "description"
COL_EXPECTED_RESULT = ("expected result", "expected")
COL_EXECUTION_STATUS = ("execution status", "status")

# ─── SYSTEM DEFAULTS ─────────────────────────────────────────────────────────
UNKNOWN_FEATURE_REF = "UNKNOWN"
DEFAULT_PROJECT_NAME = "ShopSphere"
DEFAULT_VERSION = "2.0"
DEFAULT_OUTPUT_FILENAME = "shopsphere_parsed.json"
