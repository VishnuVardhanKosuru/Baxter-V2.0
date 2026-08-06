"""
models.py
─────────
Structured Data Models (DTOs) for parsed document entities and JSON response payloads.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class FeatureModel:
    """Represents a Functional Requirement (FR) extracted from FRD."""
    feature_id: str
    feature_name: str
    description: str = ""
    actors: List[str] = field(default_factory=list)
    pre_conditions: List[str] = field(default_factory=list)
    trigger: str = ""
    main_flow: List[str] = field(default_factory=list)
    exception_flow: List[str] = field(default_factory=list)
    post_conditions: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)
    priority: str = ""


@dataclass
class FeatureContextModel:
    """Encapsulates FRD domain context merged into a TestCaseModel for LLM prompts."""
    feature_name: str = ""
    description: str = ""
    actors: List[str] = field(default_factory=list)
    pre_conditions: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)
    exception_flows: List[str] = field(default_factory=list)


@dataclass
class TestCaseModel:
    """Represents a Manual Test Case extracted from Test Cases document, enriched with FRD context."""
    tc_id: str
    title: str
    type: List[str] = field(default_factory=list)
    subject: str = ""
    feature_ref: str = ""
    execution_status: str = ""
    steps: List[str] = field(default_factory=list)
    expected_result: str = ""
    cucumber_tags: List[str] = field(default_factory=list)
    feature_context: Optional[FeatureContextModel] = None


@dataclass
class ParserSummaryModel:
    """Represents summary stats for execution output."""
    total_test_cases: int
    skipped_types: List[str] = field(default_factory=list)


@dataclass
class ParsedDocumentResponse:
    """Root JSON Output Response Body Schema (Contains enriched test cases)."""
    project: str
    version: str
    summary: ParserSummaryModel
    test_cases: List[TestCaseModel]

    def to_dict(self) -> Dict[str, Any]:
        """Recursively convert dataclass tree to dictionary."""
        return asdict(self)
