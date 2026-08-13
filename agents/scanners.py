"""
agents/scanners.py
──────────────────
Implements folder scanning, document classification, and multi-file .docx extraction 
for the Version 2 Parser Engine.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass

import docx
from docx.table import Table as DocxTable

from core import constants as const
from core.models import (
    SectionNode,
    DocumentAST,
    TestCaseModel,
)


@dataclass
class ModulePackage:
    """Represents a discovered module folder with classified .docx files."""
    module_folder: str
    frd_files: List[Path]
    tc_files: List[Path]


class DocumentClassifier:
    """Classifies .docx files within a module folder as FRD or Test Case suite."""
    
    @staticmethod
    def classify_files(folder_path: Path) -> Tuple[List[Path], List[Path]]:
        frd_files = []
        tc_files = []
        
        for file in folder_path.glob("*.docx"):
            if file.name.startswith("~$"):
                continue  # Skip temp word files
                
            name_lower = file.name.lower()
            
            if any(kw in name_lower for kw in const.FRD_FILENAME_KEYWORDS):
                frd_files.append(file)
            elif any(kw in name_lower for kw in const.TC_FILENAME_KEYWORDS):
                tc_files.append(file)
                
        return frd_files, tc_files


class ModuleFolderScanner:
    """Scans the root modules directory for module subfolders."""
    
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        
    def scan(self) -> List[ModulePackage]:
        packages = []
        if not self.root_dir.exists():
            print(f"[ERROR] Directory not found: {self.root_dir}")
            return packages
            
        for item in self.root_dir.iterdir():
            if item.is_dir():
                frd_files, tc_files = DocumentClassifier.classify_files(item)
                if frd_files or tc_files:
                    packages.append(ModulePackage(
                        module_folder=item.name,
                        frd_files=frd_files,
                        tc_files=tc_files
                    ))
        
        return packages


def split_list_field(text: str) -> List[str]:
    parts = const.REGEX_DELIMITER_SPLIT.split(text or "")
    return [p.strip().strip(",").strip() for p in parts if p.strip().strip(",").strip()]


def split_numbered_steps(text: str) -> List[str]:
    cleaned = const.REGEX_WHITESPACE.sub(" ", (text or "").strip())
    return [p.strip() for p in const.REGEX_NUMBERED_STEPS.split(cleaned) if p.strip()]


class FRDModuleParser:
    """Extracts a .docx FRD into a structured DocumentAST."""
    
    @staticmethod
    def parse(file_path: Path, module_folder: str) -> DocumentAST:
        ast = DocumentAST(module_folder=module_folder, source_file=file_path.name)
        try:
            doc = docx.Document(str(file_path))
        except Exception as e:
            print(f"  [ERROR] Failed to read FRD docx {file_path.name}: {e}")
            return ast
            
        current_section = SectionNode(
            section_id=f"{module_folder}:GEN-001",
            title="Document Header & Overview",
            type="general",
            module_folder=module_folder,
            source_file=file_path.name
        )
        ast.sections.append(current_section)
        
        def derive_section_id(title: str, index: int) -> Tuple[str, str]:
            title_lower = title.lower()
            if const.HEADING_REQUIREMENT_KEYWORD.lower() in title_lower:
                match = const.REGEX_REQUIREMENT_ID.search(title)
                if match:
                    return match.group(1).strip(), "functional"
                return f"FR-{str(index).zfill(3)}", "functional"
            elif "scope" in title_lower:
                return "SCOPE", "scope"
            elif "purpose" in title_lower:
                return "PURPOSE", "general"
            elif "interface" in title_lower:
                return "INTF", "interface"
            elif "performance" in title_lower:
                return "PERF", "nfr"
            elif "non-functional" in title_lower or "nfr" in title_lower or "security" in title_lower:
                return "NFR", "nfr"
            elif "glossary" in title_lower:
                return "GLOSSARY", "general"
            else:
                clean_title = re.sub(r"^[0-9\.\s]+", "", title).strip()
                slug = re.sub(r"[^\w]+", "_", clean_title.lower()).strip("_")[:15].upper()
                return slug or f"SEC-{index}", "general"

        for child in doc.element.body:
            local_tag = child.tag.split("}")[-1]
            
            if local_tag == const.XML_PARAGRAPH_TAG:
                p_text = "".join(
                    node.text or ""
                    for node in child.iter()
                    if node.tag.endswith(const.XML_TEXT_TAG_SUFFIX)
                ).strip()
                if not p_text:
                    continue
                    
                is_heading = False
                style_node = child.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pStyle")
                if style_node is not None:
                    val = style_node.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "")
                    if "Heading" in val:
                        is_heading = True
                        
                if const.HEADING_REQUIREMENT_KEYWORD in p_text or is_heading:
                    sec_id_suffix, sec_type = derive_section_id(p_text, len(ast.sections))
                    sec_id = f"{module_folder}:{sec_id_suffix}"
                    current_section = SectionNode(
                        section_id=sec_id,
                        title=p_text,
                        type=sec_type,
                        module_folder=module_folder,
                        source_file=file_path.name
                    )
                    ast.sections.append(current_section)
                else:
                    current_section.paragraphs.append(p_text)
                    
            elif local_tag == const.XML_TABLE_TAG:
                table = DocxTable(child, doc)
                table_rows = []
                meta = current_section.metadata
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if len(cells) >= 2:
                        key = cells[0].lower().rstrip(":")
                        val = cells[1]
                        
                        if const.KEY_DESCRIPTION in key:
                            meta["description"] = val
                        elif const.KEY_ACTORS in key:
                            meta["actors"] = [a.strip() for a in const.REGEX_TYPE_SPLIT.split(val) if a.strip()]
                        elif const.KEY_TRIGGER in key:
                            meta["trigger"] = val
                        elif const.KEY_PRIORITY in key:
                            meta["priority"] = val
                        elif any(k in key for k in const.KEY_PRECONDITIONS):
                            meta["pre_conditions"] = split_list_field(val)
                        elif const.KEY_BUSINESS_RULES in key:
                            meta["business_rules"] = split_list_field(val)
                        elif any(k in key for k in const.KEY_EXCEPTION_FLOW):
                            meta["exception_flows"] = split_numbered_steps(val)
                        elif const.KEY_MAIN_FLOW in key:
                            meta["main_flow"] = split_numbered_steps(val)
                        elif any(k in key for k in const.KEY_POSTCONDITIONS):
                            meta["post_conditions"] = split_list_field(val)
                        table_rows.append(cells)
                if table_rows:
                    current_section.tables.append(table_rows)
                    
        return ast


class TestCaseModuleParser:
    """Extracts all test cases from all tables in a .docx file."""
    
    @staticmethod
    def parse(file_path: Path, module_folder: str) -> List[TestCaseModel]:
        test_cases = []
        try:
            doc = docx.Document(str(file_path))
        except Exception as e:
            print(f"  [ERROR] Failed to read TC docx {file_path.name}: {e}")
            return test_cases
            
        if not doc.tables:
            return test_cases
            
        for table_idx, table in enumerate(doc.tables):
            if not table.rows:
                continue
                
            header_row = table.rows[0]
            headers = [(cell.text or "").strip().lower() for cell in header_row.cells]
            
            def find_col(targets) -> Optional[int]:
                targets_tuple = (targets,) if isinstance(targets, str) else targets
                for idx, h in enumerate(headers):
                    if any(t == h or (len(t) > 3 and t in h) for t in targets_tuple):
                        return idx
                return None

            col_map = {
                "test_name": find_col(const.COL_TEST_NAME),
                "type": find_col(["type", "category"]),
                "subject": find_col(["subject", "module"]),
                "description": find_col(const.COL_DESCRIPTION),
                "expected_result": find_col(const.COL_EXPECTED_RESULT),
                "execution_status": find_col(const.COL_EXECUTION_STATUS),
            }
            
            if col_map["test_name"] is None:
                continue  # Not a test case table
                
            for row_idx, row in enumerate(table.rows[1:], start=1):
                cells = [(cell.text or "").strip() for cell in row.cells]
                
                def get_val(key):
                    idx = col_map.get(key)
                    return cells[idx] if idx is not None and idx < len(cells) else ""
                    
                tc_name_full = get_val("test_name")
                if not tc_name_full:
                    continue
                    
                tc_id_match = const.REGEX_TC_ID.search(tc_name_full)
                tc_id = tc_id_match.group(1).upper() if tc_id_match else f"TC-UNKN-{row_idx}"
                title_match = const.REGEX_TC_TITLE.search(tc_name_full)
                title = title_match.group(1).strip() if title_match else tc_name_full
                
                type_str = get_val("type")
                types = [t.strip() for t in const.REGEX_TYPE_SPLIT.split(type_str) if t.strip()]
                
                desc_text = get_val("description")
                steps = split_numbered_steps(desc_text)
                if not steps and desc_text:
                    steps = [desc_text]
                    
                expected_result = get_val("expected_result")
                
                tc = TestCaseModel(
                    tc_id=tc_id,
                    title=title,
                    module_folder=module_folder,
                    source_file=file_path.name,
                    source_table_index=table_idx,
                    source_row_index=row_idx,
                    type=types,
                    subject=get_val("subject"),
                    execution_status=get_val("execution_status"),
                    steps=steps,
                    expected_result=expected_result
                )
                test_cases.append(tc)
                
        return test_cases
