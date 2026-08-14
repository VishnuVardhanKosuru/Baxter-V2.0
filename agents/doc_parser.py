"""
agents/doc_parser.py
--------------------
Multi-module FRD + Test Case parsing pipeline for the Baxter Platform.

Optimized for token efficiency and multi-key throughput:
  - Uses LiteLLM multi-key router (Key 1, Key 2, Key 3) for least-busy load balancing.
  - Compact index and test case summaries reduce mapping prompt tokens by ~25-30%.
  - Supports LLMBundle caching and structured output parsing.

Public API:
  parse_documents(modules_dir, out_dir, ...) -> List[str]
"""
import json
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

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
from core.llm_factory import create_llm

MAPPER_SYSTEM_PROMPT = (
    "You are an expert Test Automation Architect. "
    "Map each Manual Test Case to ALL relevant FRD Section IDs from the provided Index. "
    "A test case may map to multiple sections (e.g. Functional Requirement, NFR, Scope). "
    "Return all mapped references per test case with confidence score (0.0-1.0) and a 1-sentence reason."
)

MAPPER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", MAPPER_SYSTEM_PROMPT),
    ("user", "FRD Index:\n{index}\n\nTest Cases to Map:\n{test_cases}")
])

_mapper_chain = None

def _get_mapper_chain():
    """Lazy initialization of the multi-key LiteLLM mapper chain."""
    global _mapper_chain
    if _mapper_chain is None:
        bundle = create_llm()
        llm = bundle.llm if hasattr(bundle, "llm") else bundle
        _mapper_chain = MAPPER_PROMPT | llm.with_structured_output(BatchMappingResponse)
    return _mapper_chain


def build_compact_section_index(ast: DocumentAST) -> str:
    """
    Builds a highly token-efficient compact index of the FRD for LLM mapping.
    Omits redundant boilerplate and retains key functional indicators.
    """
    lines = [f"Module: {ast.module_folder}"]
    for section in ast.sections:
        line = f"[{section.section_id}] {section.title} ({section.type})"
        if section.paragraphs:
            first_p = section.paragraphs[0].strip()
            if first_p:
                summary = first_p[:140] + ("..." if len(first_p) > 140 else "")
                line += f" | {summary}"
        lines.append(line)
    return "\n".join(lines)


def enrich_module_test_cases(
    test_cases: List[TestCaseModel], 
    mapping_response: BatchMappingResponse,
    ast: DocumentAST
) -> List[TestCaseModel]:
    """Merge AST context into Test Cases based on LLM mapping."""
    section_map = {sec.section_id: sec for sec in ast.sections}
    tc_mapping_dict = {m.tc_id: m for m in mapping_response.mappings}
    
    enriched_tcs = []
    for tc in test_cases:
        mapping = tc_mapping_dict.get(tc.tc_id)
        if not mapping or not mapping.mapped_refs:
            tc.feature_ref = const.UNKNOWN_FEATURE_REF
            enriched_tcs.append(tc)
            continue
            
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
    """
    Orchestrate the full multi-module parsing and mapping pipeline.
    Utilizes multi-key LiteLLM routing across all configured API keys using async batch processing.
    """
    skip_types = skip_types or []
    print(f"\n[INFO] Scanning Modules Dir: {modules_dir}")
    
    scanner = ModuleFolderScanner(Path(modules_dir))
    packages = scanner.scan()
    
    if not packages:
        print("[WARN] No module packages found.")
        return []
        
    generated_files = []
    
    # 1. Parse and Collect Inputs
    batch_inputs = []
    packages_to_process = []
    
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
            
        tc_summaries = []
        for tc in module_tcs:
            steps_preview = " ".join(tc.steps)[:120] if tc.steps else "None"
            types_str = ",".join(tc.type) if tc.type else "General"
            tc_summaries.append(
                f"[{tc.tc_id}] {tc.title} | Subj: {tc.subject} | Type: {types_str} | Steps: {steps_preview}"
            )
            
        tc_text = "\n".join(tc_summaries)
        batch_inputs.append({"index": compact_index, "test_cases": tc_text})
        packages_to_process.append((package, ast, module_tcs))
        
    if not batch_inputs:
        return []
        
    # 2. Async Batch Mapping
    from core.llm_factory import _collect_keys
    rpm = int(os.getenv("GEMINI_RPM", "50"))
    num_keys = len(_collect_keys("GEMINI_API_KEY"))
    concurrency = min(rpm * num_keys, 500) if num_keys > 0 else rpm
    
    print(f"\n[GEMINI] Batch Mapping {len(batch_inputs)} Modules Concurrently (Concurrency: {concurrency})...")
    
    chain = _get_mapper_chain()
    
    async def _async_map_all():
        return await chain.abatch(batch_inputs, config={"max_concurrency": concurrency}, return_exceptions=True)
        
    try:
        responses = asyncio.run(_async_map_all())
    except Exception as e:
        print(f"[ERROR] Batch LLM Mapping failed: {e}")
        responses = [Exception(str(e))] * len(batch_inputs)
        
    # 3. Process Responses and Generate Artifacts
    for idx, (package, ast, module_tcs) in enumerate(packages_to_process):
        response = responses[idx]
        if isinstance(response, Exception):
            print(f"\n[ERROR] Mapping failed for {package.module_folder}: {response}")
            mapping_response = BatchMappingResponse(mappings=[])
        else:
            mapping_response = response
            
        print(f"\n[ENRICH] Merging Context for {package.module_folder}...")
        enriched = enrich_module_test_cases(module_tcs, mapping_response, ast)
        
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
                                
        module_slug = "".join([c if c.isalnum() else "_" for c in package.module_folder.lower()]).strip("_")
        module_filename = f"{module_slug}_knowledge.json"
        knowledge_dir = os.path.join(out_dir, "knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)
        module_out_path = os.path.join(knowledge_dir, module_filename)
        
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
    print(f"  Total Module JSON files generated : {len(generated_files)}")
    print(f"  Output directory                  : {os.path.join(out_dir, 'knowledge')}")
    
    return generated_files

