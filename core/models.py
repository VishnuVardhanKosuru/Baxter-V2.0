"""
core/models.py
──────────────
Structured Data Models (DTOs) and schemas for parsed document entities,
test cases, and JSON response payloads across the platform.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field as PydanticField


# ─── FRD & PARSER DATA MODELS (DTOs) ──────────────────────────────────────────

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


# ─── CODE GENERATOR STRUCTURED OUTPUT SCHEMAS ─────────────────────────────────

class TestCaseRow(BaseModel):
    """One row in expected.csv — represents a single test step."""
    testcase:          str = PydanticField(description="Test case ID and title, e.g. 'TC-001 - User Registration'")
    description:       str = PydanticField(description="Detailed objective of the test case")
    category:          str = PydanticField(description="Test type/category e.g. 'UI Form Validation'")
    preconditions:     str = PydanticField(description="Pre-requisites before executing this step")
    stepname:          str = PydanticField(description="The exact action/step being performed")
    expected_result:   str = PydanticField(description="Expected system response or outcome for this step")
    testdata:          str = PydanticField(description="Specific input data, e.g. 'email: test@example.com | password: Test@123'")
    evidence_required: str = PydanticField(description="Proof needed, e.g. 'Screenshot of success toast', '200 OK in Network tab'")


class FullTestCaseOutput(BaseModel):
    """
    Single structured response from the LLM containing all 3 generated artifacts.
    Generated in one shared context window so Selenium script aligns with Gherkin steps.
    """
    csv_rows: List[TestCaseRow] = PydanticField(
        description="Ordered step-by-step rows to write into expected.csv"
    )
    cucumber_feature: str = PydanticField(
        description=(
            "Complete raw Gherkin .feature file content. "
            "No markdown fences. Start directly with tags/Feature keyword."
        )
    )
    selenium_script: str = PydanticField(
        description=(
            "Complete raw Python Selenium test script implementing every Gherkin step. "
            "No markdown fences. Start directly with the module docstring or import."
        )
    )
