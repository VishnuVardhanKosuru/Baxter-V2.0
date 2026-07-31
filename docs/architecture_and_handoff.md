# Code Knowledge Base Scanner: Architecture & Handoff Document

This document captures the complete architectural decisions, constraints, and current state of the KB Scanner project. It is designed to be fed to another Antigravity AI agent to immediately resume work with full context.

## 1. Project Goal
Build a local client that orchestrates a remote security and AST scanner for GitHub repositories. The scanner produces a structured Knowledge Base (`kb.json`) that can be consumed by other AI agents (e.g., a Tester Agent) to automatically generate unit tests, integration tests, and security fixes.

## 2. Core Security Constraint
> [!IMPORTANT]
> **"Code Never Touches the Local Machine."**
> For privacy and security compliance, proprietary source code cannot be cloned or downloaded to the local client's file system. All parsing and scanning must occur securely in the cloud, with only metadata and targeted insights returning to the local machine.

## 3. Architecture Overview
Because of the core constraint, the architecture relies heavily on GitHub Actions.
1. **Local Orchestrator (`scanner.py`)**: A Python CLI tool that runs locally. It authenticates with a GitHub Personal Access Token (PAT).
2. **Setup Phase**: The local client securely commits two files to the target repository via the GitHub REST API:
   - `.github/workflows/kb-scanner.yml` (The GitHub Action workflow)
   - `.github/scripts/extract_ast.py` (The Tree-sitter parser)
3. **Execution Phase**: The local client triggers the workflow (`workflow_dispatch`) and polls the API for completion. 
4. **Cloud Execution**:
   - **Job 1 (Tree-sitter)**: Parses the code into an AST and generates `ast.json`.
   - **Job 2 (CodeQL)**: Scans for vulnerabilities. We use `build-mode: none` so CodeQL successfully scans compiled languages (Java, C#) without requiring a `pom.xml` or custom build step. Generates `sarif-results`.
5. **Download & Merge Phase**: Once the workflow succeeds, the local client downloads the ZIP artifacts *directly into memory* (never writing the raw zip to disk). It merges the AST and SARIF data into a single `kb.json` file on the local machine.

## 4. The Knowledge Base (`kb.json`)
The resulting output provides a structured map of the repository.
```json
{
  "repo": "owner/repo",
  "summary": { "total_files": 4, "total_vulnerabilities": 0 },
  "files": [
    {
      "path": "src/DBConnection.java",
      "language": "java",
      "ast": {
        "functions": [
          {
            "name": "getConnection",
            "line_start": 9,
            "line_end": 19,
            "body": "public Connection getConnection() { ... }"
          }
        ],
        "classes": [],
        "imports": []
      },
      "vulnerabilities": []
    }
  ]
}
```

## 5. Key Trade-offs & Iterations
* **CodeQL Autobuild vs Build-Mode None**: We initially used `autobuild` for CodeQL. This failed on a Java repository (`LibraryManagementSystem`) because it lacked a standard build system (Maven/Gradle). We iterated by switching to `build-mode: none`, which tells CodeQL to scan Java without compiling it. This makes the scanner universally compatible across languages.
* **AST Extraction Depth**: Initially, the AST extractor only pulled function names and line numbers to strictly adhere to the "no code on local machine" rule. However, to support an AI **Tester Agent**, we realized the AI *needs* the function logic to write meaningful white-box unit tests. We compromised by extracting the **Method Bodies** into the JSON, accepting that fragments of source code will exist in the JSON, but the raw repo is never cloned.

## 6. Future Roadmap: The Tester Agent
To manage the fact that extracting method bodies significantly increases the size of `kb.json`, the future Tester Agent must follow a **Retrieval-Augmented Generation (RAG)** approach:
1. Parse `kb.json` locally.
2. Read the function *signatures* and names to understand the repo map.
3. Select a specific function to test.
4. Retrieve only that specific function's `body` from the JSON to inject into the LLM prompt.
*(Do not feed the entire `kb.json` into the LLM context window at once).*

## 7. Current Project Directory State
* `scanner.py` - The main CLI entry point.
* `github_client.py` - Custom wrapper for GitHub REST API (handles rate limits).
* `workflow_manager.py` - Commits templates and triggers the Action.
* `artifact_downloader.py` - Downloads/unzips artifacts in memory.
* `kb_merger.py` - Merges AST and SARIF JSONs.
* `templates/kb-scanner.yml` - The GitHub Actions workflow (uses `build-mode: none`).
* `templates/extract_ast.py` - The tree-sitter script that runs remotely.
* `.env` - Stores `GITHUB_PAT`.
