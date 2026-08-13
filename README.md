# Baxter: Version 2 Parser Engine

Stage 1 Dual-Document AST Parser & Context Enrichment Engine for Functional Requirements Documents (FRD) and Manual Test Cases (`.docx`).

---

## 📁 Directory Structure

```text
Version 2 Parser/
├── agents/
│   ├── doc_parser.py     # Stage 1: Document AST Parser & Fuzzy Context Enrichment Agent
│   └── __init__.py       # Agents package initializer
├── core/
│   ├── constants.py      # Regexes, default paths, and configuration constants
│   ├── models.py         # Structured Pydantic & dataclass schemas (DTOs)
│   └── __init__.py       # Core package initializer
├── Documentation/        # Comprehensive architecture & optimization documentation
├── input_modules/        # Directory containing subfolders with .docx FRD & Test Cases
├── output/               # Destination directory for generated structured JSON files
├── main.py               # CLI runner to execute document parsing
├── requirements.txt      # Python dependencies (python-docx, pydantic, etc.)
└── .gitignore            # Git ignore configuration
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Parser
You can run the parser directly on the input modules directory:

```bash
# Run on the default input_modules/ directory
python main.py

# Run with a custom input directory
python main.py --modules-dir "path/to/my_modules" --out "./output"
```

### 3. Programmatic Usage in Python
```python
from agents.doc_parser import parse_documents

json_output_paths = parse_documents(
    modules_dir="input_modules",
    out_dir="output",
    project="ShopSphere"
)
print(f"Parsed JSON files generated at: {json_output_paths}")
```
