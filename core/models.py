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
class SectionNode:
    """Represents any section in the FRD (Scope, Interface, NFR, etc.)."""
    section_id: str
    title: str
    type: str  # 'functional', 'nfr', 'interface', 'glossary', 'metadata', 'general'
    module_folder: str = ""
    source_file: str = ""
    paragraphs: List[str] = field(default_factory=list)
    tables: List[List[Dict[str, str]]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentAST:
    """Represents a fully extracted FRD document tree."""
    module_folder: str
    source_file: str
    sections: List[SectionNode] = field(default_factory=list)


@dataclass
class FeatureContextModel:
    """Rich domain context extracted from an FRD section for a specific feature."""
    feature_name: str
    description: str
    trigger: str = ""
    priority: str = ""
    actors: List[str] = field(default_factory=list)
    pre_conditions: List[str] = field(default_factory=list)
    main_flow: List[str] = field(default_factory=list)
    post_conditions: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)
    exception_flows: List[str] = field(default_factory=list)

@dataclass
class MappedContextModel:
    """Encapsulates AI mapping decision and full extracted domain context for a specific mapped FRD section."""
    ref_id: str
    title: str
    type: str
    confidence: float
    reason: str
    context: Optional[FeatureContextModel] = None


@dataclass
class TestCaseModel:
    """Represents a Manual Test Case extracted from Test Cases document, enriched with FRD context."""
    tc_id: str
    title: str
    module_folder: str = ""
    source_file: str = ""
    source_table_index: int = -1
    source_row_index: int = -1
    type: List[str] = field(default_factory=list)
    subject: str = ""
    feature_ref: str = ""
    feature_refs: List[str] = field(default_factory=list)
    execution_status: str = ""
    steps: List[str] = field(default_factory=list)
    expected_result: str = ""
    cucumber_tags: List[str] = field(default_factory=list)
    mapped_contexts: List[MappedContextModel] = field(default_factory=list)


# ─── GEMINI MAPPING STRUCTURED OUTPUT SCHEMAS ─────────────────────────────────

class MappedRef(BaseModel):
    ref_id: str = PydanticField(description="ID of mapped section e.g. FR-001, NFR-SEC, INTF-SENDGRID")
    confidence: float = PydanticField(description="Confidence score 0.0 to 1.0")
    reason: str = PydanticField(description="1-sentence reason for mapping")

class TestCaseMapping(BaseModel):
    tc_id: str = PydanticField(description="Test case ID e.g. TC-001")
    mapped_refs: List[MappedRef]

class BatchMappingResponse(BaseModel):
    mappings: List[TestCaseMapping]


@dataclass
class ParserSummaryModel:
    """Represents summary stats for execution output."""
    total_test_cases: int
    skipped_types: List[str] = field(default_factory=list)


@dataclass
class ModuleOverviewModel:
    """Represents global document metadata extracted from general FRD sections (Purpose, Scope, Glossary)."""
    purpose: str = ""
    in_scope: List[str] = field(default_factory=list)
    out_of_scope: List[str] = field(default_factory=list)
    glossary: Dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedDocumentResponse:
    """Root JSON Output Response Body Schema (Contains enriched test cases)."""
    project: str
    version: str
    module_overview: Optional[ModuleOverviewModel]
    summary: ParserSummaryModel
    test_cases: List[TestCaseModel]

    def to_dict(self) -> Dict[str, Any]:
        """Recursively convert dataclass tree to dictionary, stripping empty fields."""
        def exclude_empty(data):
            return {k: v for k, v in data if v or v is False or v == 0}
        return asdict(self, dict_factory=exclude_empty)


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
