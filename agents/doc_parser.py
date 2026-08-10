"""
doc_parser.py
─────────────
Parses a Functional Requirements Document (FRD) and a Manual Test Cases
document (both .docx) and produces a structured JSON output.
"""

import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import docx
from docx.table import Table as DocxTable

# Force UTF-8 output for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import core.constants as const
    from core.models import (
        FeatureModel,
        FeatureContextModel,
        TestCaseModel,
        ParserSummaryModel,
        ParsedDocumentResponse,
    )
except ImportError:
    _root = Path(__file__).parent.parent.resolve()
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    import core.constants as const
    from core.models import (
        FeatureModel,
        FeatureContextModel,
        TestCaseModel,
        ParserSummaryModel,
        ParsedDocumentResponse,
    )


# ─── TEXT UTILITIES ───────────────────────────────────────────────────────────

def clean(text: str) -> str:
    """Collapse internal whitespace and strip leading/trailing spaces."""
    return const.REGEX_WHITESPACE.sub(" ", (text or "").strip())


def split_numbered_steps(text: str) -> List[str]:
    """Split a numbered step string ('1. Step one\n2. Step two') into a list."""
    text = clean(text)
    return [p.strip() for p in const.REGEX_NUMBERED_STEPS.split(text) if p.strip()]


def split_list_field(text: str) -> List[str]:
    """Split string by semicolons or newlines into clean list items."""
    parts = const.REGEX_DELIMITER_SPLIT.split(text)
    return [p.strip().strip(",").strip() for p in parts if p.strip().strip(",").strip()]


def parse_type_list(type_str: str) -> List[str]:
    """Split type string 'Functional / Smoke' into ['Functional', 'Smoke']."""
    return [t.strip() for t in const.REGEX_TYPE_SPLIT.split(type_str) if t.strip()]


def should_skip(type_str: str, skip_types: List[str]) -> bool:
    """Check if type string contains any of the target skip keywords."""
    type_lower = type_str.lower()
    return any(s.strip().lower() in type_lower for s in skip_types if s.strip())


def slugify(text: str) -> str:
    """Convert text into clean snake_case slug suitable for tags."""
    return (
        text.lower()
        .strip()
        .replace(" ", "_")
        .replace("&", "and")
        .replace("—", "")
        .replace("-", "")
        .replace("/", "")
    )


def build_cucumber_tags(types: List[str], subject: str, feature_ref: str = "") -> List[str]:
    """Build unique list of Cucumber @tags from test type, subject, and feature ID."""
    tags = []
    for t in types:
        tag_slug = slugify(t)
        if tag_slug:
            tags.append(f"@{tag_slug}")

    subject_slug = slugify(subject)
    if subject_slug:
        tags.append(f"@{subject_slug}")

    if feature_ref and feature_ref != const.UNKNOWN_FEATURE_REF:
        tags.append(f"@{feature_ref.lower().replace('-', '_')}")

    return list(dict.fromkeys(tags))


# ─── FRD PARSER ENGINE ────────────────────────────────────────────────────────

def iter_body_elements(doc):
    """Yield (tag, element) tuples for block-level elements in document body."""
    body = doc.element.body
    for child in body:
        local_tag = child.tag.split("}")[-1]
        if local_tag in (const.XML_PARAGRAPH_TAG, const.XML_TABLE_TAG):
            yield ("paragraph" if local_tag == const.XML_PARAGRAPH_TAG else "table"), child


def get_paragraph_text(p_element) -> str:
    """Extract full concatenated text from a paragraph XML element."""
    return "".join(
        node.text or ""
        for node in p_element.iter()
        if node.tag.endswith(const.XML_TEXT_TAG_SUFFIX)
    )


def parse_frd(frd_path: str) -> Tuple[List[FeatureModel], Dict[str, str], Dict[str, FeatureModel]]:
    """
    Dynamically parse FRD document into FeatureModel DTOs and lookup maps.

    Returns:
        features          (List[FeatureModel])      — List of parsed feature DTOs
        feature_name_map  (Dict[str, str])          — Lowercase feature name → feature_id
        features_by_id    (Dict[str, FeatureModel]) — feature_id → FeatureModel DTO
    """
    doc = docx.Document(frd_path)
    features: List[FeatureModel] = []
    feature_name_map: Dict[str, str] = {}
    features_by_id: Dict[str, FeatureModel] = {}

    pending_feature: Optional[FeatureModel] = None

    for kind, element in iter_body_elements(doc):
        if kind == "paragraph":
            text = clean(get_paragraph_text(element))

            if const.HEADING_REQUIREMENT_KEYWORD in text:
                if pending_feature is not None:
                    features.append(pending_feature)
                    feature_name_map[pending_feature.feature_name.lower()] = pending_feature.feature_id
                    features_by_id[pending_feature.feature_id] = pending_feature

                match = const.REGEX_REQUIREMENT_ID.search(text)
                if match:
                    feature_id = match.group(1).strip()
                    feature_name = clean(match.group(2))
                else:
                    feature_id = f"FR-{str(len(features) + 1).zfill(3)}"
                    feature_name = text

                pending_feature = FeatureModel(
                    feature_id=feature_id,
                    feature_name=feature_name,
                )

        elif kind == "table" and pending_feature is not None:
            table = DocxTable(element, doc)

            for row in table.rows:
                cells = row.cells
                if len(cells) < 2:
                    continue

                key = clean(cells[0].text).lower().rstrip(":")
                value = clean(cells[1].text)

                if not key or not value:
                    continue

                if const.KEY_DESCRIPTION in key:
                    pending_feature.description = value
                elif const.KEY_ACTORS in key:
                    pending_feature.actors = [
                        a.strip() for a in const.REGEX_TYPE_SPLIT.split(value) if a.strip()
                    ]
                elif any(k in key for k in const.KEY_PRECONDITIONS):
                    pending_feature.pre_conditions = split_list_field(value)
                elif const.KEY_TRIGGER in key:
                    pending_feature.trigger = value
                elif const.KEY_MAIN_FLOW in key:
                    pending_feature.main_flow = split_numbered_steps(value)
                elif any(k in key for k in const.KEY_EXCEPTION_FLOW):
                    pending_feature.exception_flow = split_numbered_steps(value)
                elif any(k in key for k in const.KEY_POSTCONDITIONS):
                    pending_feature.post_conditions = split_list_field(value)
                elif const.KEY_BUSINESS_RULES in key:
                    pending_feature.business_rules = split_list_field(value)
                elif const.KEY_PRIORITY in key:
                    pending_feature.priority = value

            features.append(pending_feature)
            feature_name_map[pending_feature.feature_name.lower()] = pending_feature.feature_id
            features_by_id[pending_feature.feature_id] = pending_feature

            print(f"  [FRD] {pending_feature.feature_id} - {pending_feature.feature_name}")
            pending_feature = None

    if pending_feature is not None:
        features.append(pending_feature)
        feature_name_map[pending_feature.feature_name.lower()] = pending_feature.feature_id
        features_by_id[pending_feature.feature_id] = pending_feature

    return features, feature_name_map, features_by_id


# ─── FUZZY MATCHING ENGINE ────────────────────────────────────────────────────

def match_subject_to_feature(subject: str, feature_name_map: Dict[str, str]) -> str:
    """Match test case subject to closest FRD feature_id using a 3-tier algorithm."""
    subject_lower = subject.lower().strip()
    names_lower = list(feature_name_map.keys())

    # Tier 1: Substring match
    for name in names_lower:
        if subject_lower in name or name in subject_lower:
            return feature_name_map[name]

    # Tier 2: Stemmed word overlap match
    subject_words = set(const.REGEX_NON_ALPHANUM.split(subject_lower))
    best_overlap = 0
    best_match = None
    for name in names_lower:
        name_words = set(const.REGEX_NON_ALPHANUM.split(name))
        overlap = sum(
            1 for sw in subject_words
            for nw in name_words
            if sw and nw and (sw in nw or nw in sw)
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = name

    if best_match and best_overlap > 0:
        return feature_name_map[best_match]

    # Tier 3: Levenshtein distance similarity match
    matches = difflib.get_close_matches(subject_lower, names_lower, n=1, cutoff=0.4)
    if matches:
        return feature_name_map[matches[0]]

    return const.UNKNOWN_FEATURE_REF


# ─── MANUAL TEST CASE PARSER & ENRICHER ────────────────────────────────────────

def resolve_column_indexes(header_row) -> Dict[str, int]:
    """Map header row text to column index positions."""
    headers = [clean(cell.text).lower() for cell in header_row.cells]
    col_map = {}

    def find_idx(targets) -> Optional[int]:
        targets_tuple = (targets,) if isinstance(targets, str) else targets
        for idx, h in enumerate(headers):
            if any(t in h for t in targets_tuple):
                return idx
        return None

    col_map["test_name"] = find_idx(const.COL_TEST_NAME)
    col_map["type"] = find_idx(const.COL_TYPE)
    col_map["subject"] = find_idx(const.COL_SUBJECT)
    col_map["description"] = find_idx(const.COL_DESCRIPTION)
    col_map["expected_result"] = find_idx(const.COL_EXPECTED_RESULT)
    col_map["execution_status"] = find_idx(const.COL_EXECUTION_STATUS)
    return col_map


def parse_test_cases(
    tc_path: str,
    feature_name_map: Dict[str, str],
    features_by_id: Dict[str, FeatureModel],
    skip_types: List[str]
) -> List[TestCaseModel]:
    """Dynamically parse Manual Test Cases document and enrich each test case with FRD context."""
    doc = docx.Document(tc_path)

    if not doc.tables:
        print("  [WARN] No tables found in the TC document.")
        return []

    table = doc.tables[0]
    col_idx = resolve_column_indexes(table.rows[0])
    test_cases: List[TestCaseModel] = []

    for row in table.rows[1:]:
        cells = [clean(cell.text) for cell in row.cells]

        def get_val(key: str) -> str:
            idx = col_idx.get(key)
            return cells[idx] if idx is not None and idx < len(cells) else ""

        tc_name_full = get_val("test_name")
        type_str = get_val("type")
        subject = get_val("subject")
        description = get_val("description")
        expected_result = get_val("expected_result")
        execution_status = get_val("execution_status")

        if not tc_name_full:
            continue

        tc_id_match = const.REGEX_TC_ID.search(tc_name_full)
        if not tc_id_match:
            continue
        tc_id = tc_id_match.group(1).upper()

        if type_str and should_skip(type_str, skip_types):
            print(f"  [SKIP] Skipping {tc_id} (type: {type_str})")
            continue

        title_match = const.REGEX_TC_TITLE.search(tc_name_full)
        title = clean(title_match.group(1)) if title_match else tc_name_full

        types = parse_type_list(type_str)
        steps = split_numbered_steps(description)
        feature_ref = match_subject_to_feature(subject, feature_name_map)
        tags = build_cucumber_tags(types, subject, feature_ref)

        feature_context = None
        if feature_ref in features_by_id:
            parent = features_by_id[feature_ref]
            feature_context = FeatureContextModel(
                feature_name=parent.feature_name,
                description=parent.description,
                actors=parent.actors,
                pre_conditions=parent.pre_conditions,
                business_rules=parent.business_rules,
                exception_flows=parent.exception_flow,
            )

        tc_model = TestCaseModel(
            tc_id=tc_id,
            title=title,
            type=types,
            subject=subject,
            feature_ref=feature_ref,
            execution_status=execution_status,
            steps=steps,
            expected_result=expected_result,
            cucumber_tags=tags,
            feature_context=feature_context,
        )

        test_cases.append(tc_model)
        print(f"  [TC] {tc_id} - {title} [-> {feature_ref} (Enriched)]")

    return test_cases


# ─── MAIN EXECUTION ───────────────────────────────────────────────────────────

def parse_documents(
    frd_path: str,
    tc_path: str,
    out_dir: str,
    project: str = "",
    version: str = const.DEFAULT_VERSION,
    skip_types: Optional[List[str]] = None,
) -> str:
    """
    Importable API — parses FRD + TC docs and writes structured JSON.
    Returns the absolute path to the generated JSON file.

    Called directly by server.py (no subprocess / CLI needed).
    """
    skip_types = skip_types or []

    # Derive project name and output filename dynamically from FRD stem
    frd_stem = Path(frd_path).stem
    project_name = (
        project
        if project
        else frd_stem.replace("_", " ").split("Functional")[0].strip() or frd_stem
    )
    safe_slug = re.sub(r"[^\w]+", "_", project_name.lower()).strip("_")
    output_filename = f"{safe_slug}_parsed.json"

    print(f"\n[INFO] FRD File : {frd_path}")
    print(f"[INFO] TC File  : {tc_path}")
    print(f"[INFO] Out Dir  : {out_dir}")
    print(f"[INFO] Project  : {project_name}")
    print(f"[INFO] Skip     : {skip_types or 'None'}\n")

    print("[PARSING] Parsing FRD...")
    features, feature_name_map, features_by_id = parse_frd(frd_path)

    print("\n[PARSING] Parsing & Enriching Manual Test Cases with FRD Context...")
    test_cases = parse_test_cases(tc_path, feature_name_map, features_by_id, skip_types)

    response_payload = ParsedDocumentResponse(
        project=project_name,
        version=version,
        summary=ParserSummaryModel(
            total_test_cases=len(test_cases),
            skipped_types=skip_types,
        ),
        test_cases=test_cases,
    )

    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(response_payload.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Document Parsing Complete!")
    print(f"  Features parsed              : {len(features)}")
    print(f"  Test cases parsed & enriched : {len(test_cases)}")
    print(f"  Output saved to              : {output_path}")

    return output_path
