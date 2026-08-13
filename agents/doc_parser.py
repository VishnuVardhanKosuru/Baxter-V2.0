"""
doc_parser.py
─────────────
Orchestrates the multi-module extraction, mapping, and enrichment pipeline.
"""
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

import core.constants as const
from core.models import (
    DocumentAST,
    TestCaseModel,
    ModuleOverviewModel,
    MappedContextModel,
    BatchMappingResponse,
    MappedRef,
    FeatureContextModel,
    ParserSummaryModel,
    ParsedDocumentResponse
)
from agents.scanners import ModuleFolderScanner, FRDModuleParser, TestCaseModuleParser

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=const.DEFAULT_MODEL,
    temperature=0.1,
    max_retries=const.MAX_LLM_RETRIES
)
structured_llm = llm.with_structured_output(BatchMappingResponse)

def build_compact_section_index(ast: DocumentAST) -> str:
    """Builds a ~800 token compact index of the FRD for the LLM."""
    lines = [f"Module: {ast.module_folder}"]
    for section in ast.sections:
        lines.append(f"[{section.section_id}] {section.title} ({section.type})")
        # Include first paragraph as summary if available
        if section.paragraphs:
            summary = section.paragraphs[0][:200] + ("..." if len(section.paragraphs[0]) > 200 else "")
            lines.append(f"  Summary: {summary}")
    return "\n".join(lines)

def map_module_test_cases_gemini(
    compact_index: str, 
    test_cases: List[TestCaseModel]
) -> BatchMappingResponse:
    """Send batched test cases to Gemini for structural mapping."""
    tc_summaries = []
    for tc in test_cases:
        steps_preview = " ".join(tc.steps)[:150] + "..." if tc.steps else "No steps"
        tc_summaries.append(f"TC ID: {tc.tc_id} | Title: {tc.title} | Subject: {tc.subject} | Types: {tc.type} | Steps Preview: {steps_preview}")
        
    tc_text = "\n".join(tc_summaries)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Test Automation Architect. "
                   "Map each Manual Test Case to ALL relevant FRD Section IDs from the provided Index. "
                   "A test case will often depend on multiple sections (e.g., a Functional Requirement AND a Security NFR AND a Scope boundary). "
                   "Return a list of ALL mapped references for each test case, along with a confidence score (0.0-1.0) and a 1-sentence reason for each mapping."),
        ("user", "FRD Index:\n{index}\n\nTest Cases to Map:\n{test_cases}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        response = chain.invoke({"index": compact_index, "test_cases": tc_text})
        return response
    except Exception as e:
        print(f"[ERROR] LLM Mapping failed: {e}")
        return BatchMappingResponse(mappings=[])

def enrich_module_test_cases(
    test_cases: List[TestCaseModel], 
    mapping_response: BatchMappingResponse,
    ast: DocumentAST
) -> List[TestCaseModel]:
    """Merge AST context into Test Cases based on LLM mapping."""
    
    # Create lookup map for sections
    section_map = {sec.section_id: sec for sec in ast.sections}
    
    # Create lookup for mappings
    tc_mapping_dict = {m.tc_id: m for m in mapping_response.mappings}
    
    enriched_tcs = []
    for tc in test_cases:
        mapping = tc_mapping_dict.get(tc.tc_id)
        if not mapping or not mapping.mapped_refs:
            tc.feature_ref = const.UNKNOWN_FEATURE_REF
            enriched_tcs.append(tc)
            continue
            
        # Capture ALL mapped references returned by Gemini with their full individual context payloads
        mapped_contexts = []
        feature_refs = []

        for ref in mapping.mapped_refs:
            clean_ref_id = ref.ref_id.strip("[]")
            feature_refs.append(clean_ref_id)
            sec = section_map.get(clean_ref_id)
            
            sec_context = None
            if sec:
                meta = sec.metadata or {}
                d = meta.get("description", "")
                if not d and sec.paragraphs:
                    d = "\n".join(sec.paragraphs[:2])
                sec_context = FeatureContextModel(
                    feature_name=sec.title,
                    description=d,
                    trigger=meta.get("trigger", ""),
                    priority=meta.get("priority", ""),
                    actors=meta.get("actors", []),
                    pre_conditions=meta.get("pre_conditions", []),
                    main_flow=meta.get("main_flow", []),
                    post_conditions=meta.get("post_conditions", []),
                    business_rules=meta.get("business_rules", []),
                    exception_flows=meta.get("exception_flows", [])
                )
                
            mapped_contexts.append(MappedContextModel(
                ref_id=ref.ref_id,
                title=sec.title if sec else "Unknown Section",
                type=sec.type if sec else "general",
                confidence=ref.confidence,
                reason=ref.reason,
                context=sec_context
            ))

        best_ref = max(mapping.mapped_refs, key=lambda x: x.confidence)
        clean_best_ref_id = best_ref.ref_id.strip("[]")
        tc.feature_ref = clean_best_ref_id
        tc.feature_refs = feature_refs
        tc.mapped_contexts = mapped_contexts
            
        # Auto-generate cucumber tags
        tag_subject = "".join([c if c.isalnum() else "_" for c in tc.subject.lower()]).strip("_")
        tag_feat = clean_best_ref_id.lower().replace("-", "_").replace(":", "_")
        tags = [f"@{t.lower()}" for t in tc.type] if tc.type else []
        if tag_subject: tags.append(f"@{tag_subject}")
        tags.append(f"@{tag_feat}")
        tc.cucumber_tags = list(dict.fromkeys(tags))
            
        enriched_tcs.append(tc)
        
    return enriched_tcs

def parse_documents(
    modules_dir: str,
    out_dir: str,
    project: str = const.DEFAULT_PROJECT_NAME,
    version: str = const.DEFAULT_VERSION,
    skip_types: Optional[List[str]] = None,
) -> List[str]:
    """Main orchestration function for multi-module parsing."""
    skip_types = skip_types or []
    print(f"\n[INFO] Scanning Modules Dir: {modules_dir}")
    
    scanner = ModuleFolderScanner(Path(modules_dir))
    packages = scanner.scan()
    
    if not packages:
        print("[WARN] No module packages found.")
        return []
        
    all_enriched_test_cases = []
    generated_files = []
    
    for package in packages:
        print(f"\n[MODULE] {package.module_folder}")
        
        if not package.frd_files or not package.tc_files:
            print(f"  [WARN] Missing FRD or TC files. Skipping.")
            continue
            
        # Parse FRD
        frd_file = package.frd_files[0]
        print(f"  [FRD] Extracting {frd_file.name}")
        ast = FRDModuleParser.parse(frd_file, package.module_folder)
        
        compact_index = build_compact_section_index(ast)
        print(f"  [FRD] Generated {len(compact_index)} char Compact Index")
        
        # Parse TCs
        module_tcs = []
        for tc_file in package.tc_files:
            print(f"  [TC] Extracting from {tc_file.name}")
            tcs = TestCaseModuleParser.parse(tc_file, package.module_folder)
            module_tcs.extend(tcs)
            
        if not module_tcs:
            print(f"  [WARN] No test cases found in module.")
            continue
            
        print(f"  [GEMINI] Mapping {len(module_tcs)} Test Cases...")
        mapping_response = map_module_test_cases_gemini(compact_index, module_tcs)
        
        # Generate slug for module outputs
        module_slug = "".join([c if c.isalnum() else "_" for c in package.module_folder.lower()]).strip("_")
        
        print(f"  [ENRICH] Merging Context...")
        enriched = enrich_module_test_cases(module_tcs, mapping_response, ast)
        all_enriched_test_cases.extend(enriched)
        
        # Extract Module Overview (Purpose, Scope, Glossary)
        overview = ModuleOverviewModel()
        for sec in ast.sections:
            title_lower = sec.title.lower()
            if "purpose" in title_lower and not overview.purpose:
                overview.purpose = "\n".join(sec.paragraphs)
            elif "scope" in title_lower:
                is_out_of_scope_section = "out of scope" in title_lower or "out-of-scope" in title_lower
                for p in sec.paragraphs:
                    p_lower = p.lower()
                    if is_out_of_scope_section or "out of scope" in p_lower or "out-of-scope" in p_lower:
                        overview.out_of_scope.append(p)
                    else:
                        overview.in_scope.append(p)
            elif "glossary" in title_lower or sec.type == "glossary":
                for table in sec.tables:
                    for row in table:
                        if len(row) >= 2:
                            term = row[0].strip()
                            definition = row[1].strip()
                            if term and term.lower() not in ["term", "acronym"]:
                                overview.glossary[term] = definition
                                
        # Build & save individual per-module JSON file
        module_filename = f"{module_slug}_knowledge.json"
        module_out_path = os.path.join(out_dir, module_filename)
        
        module_payload = ParsedDocumentResponse(
            project=f"{project} - {package.module_folder}",
            version=version,
            module_overview=overview,
            summary=ParserSummaryModel(
                total_test_cases=len(enriched),
                skipped_types=skip_types,
            ),
            test_cases=enriched,
        )
        
        try:
            with open(module_out_path, "w", encoding="utf-8") as f:
                json.dump(module_payload.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"  [SAVED] Module JSON saved: {module_out_path}")
            generated_files.append(module_out_path)
        except Exception as e:
            print(f"  [ERROR] Failed to save module JSON {module_out_path}: {e}")
            
    print(f"\n[SUCCESS] Document Parsing Complete!")
    # Remove duplicates from generated_files by wrapping in set if needed, but it shouldn't have duplicates anymore
    print(f"  Total Module JSON files generated : {len(generated_files)}")
    print(f"  Output directory                  : {out_dir}")
    
    return generated_files


