# KB-Scanner Pipeline Architecture & Workflow

This document outlines the end-to-end architecture and data flow of the KB-Scanner system. The system is designed to autonomously map a repository, integrate security vulnerabilities, and generate both automated (JUnit/Selenium/API) and manual test cases using AI.

## High-Level Architecture

The system is composed of three primary components:
1. **Pipeline Orchestrator (`pipeline.py`)**: The master controller that manages the state, calculates code deltas, and coordinates the agents.
2. **Scanner Agent (`scanner_agent.py`)**: The extractor that builds the structural Knowledge Graph (`kb.json`) and merges CodeQL vulnerability reports into it.
3. **Tester Agent (`tester_agent.py`)**: The AI engine that reads the Knowledge Graph, assigns testing strategies based on the code's context, and uses Gemini to write the actual tests.

---

## The Workflow Flowchart

```mermaid
graph TD
    %% User Input
    User((User)) -->|Runs pipeline.py| Orch[Orchestrator]
    
    %% Orchestrator Phase
    subgraph Orchestration Phase
        Orch --> CheckState{Previous scan exists?}
        CheckState -- No --> FullScan[Mode: FULL SCAN]
        CheckState -- Yes --> FetchCommits[Fetch Previous & Latest Commits]
        FetchCommits --> Compare{Latest == Previous?}
        Compare -- Yes --> Abort[Abort: No new changes]
        Compare -- No --> DeltaScan[Mode: DELTA SCAN]
    end
    
    FullScan --> Scanner
    DeltaScan --> Scanner
    
    %% Scanner Phase
    subgraph Scanner Phase
        Scanner[Scanner Agent] --> Push[Upload extract_ast.py to GitHub]
        Push --> Trigger[Trigger GitHub Action Workflow]
        Trigger --> Wait[Wait for remote AST & CodeQL extraction]
        Wait --> Download[Download artifacts: AST & SARIF]
        
        Download --> Merge[KB Merger: Inject vulnerabilities into AST nodes]
        Merge --> Output1[(Output: kb.json & graph.html)]
        Merge --> Output2[(Output: vulnerabilities_report.json)]
        Merge --> Output3[(Output: repo_structure.txt)]
    end
    
    Output1 --> Tester
    
    %% Tester Phase
    subgraph Tester Phase
        Tester[Tester Agent] --> Filter[Filter Target Files]
        
        Filter --> DeltaFilter{Is Delta Scan?}
        DeltaFilter -- Yes --> KeepChanged[Keep ONLY changed files]
        DeltaFilter -- No --> KeepAll[Keep ALL files]
        
        KeepChanged --> Strat[Strategy Injection]
        KeepAll --> Strat
        
        Strat --> WebCheck{Is UI/Frontend?}
        WebCheck -- Yes --> UIStrat[Inject Selenium UI Strategy]
        WebCheck -- No --> BackendCheck{Is Backend API?}
        
        BackendCheck -- Yes --> APIStrat[Inject API/RestAssured Strategy]
        BackendCheck -- No --> UnitStrat[Inject JUnit Strategy]
        
        UIStrat --> Gemini[Prompt Gemini AI]
        APIStrat --> Gemini
        UnitStrat --> Gemini
        
        Gemini --> FinalJava[(Automated Java Tests)]
        Gemini --> FinalCSV[(Manual Test Cases CSV)]
    end
```

---

## Component Deep Dive

### 1. Delta Testing (Orchestrator)
To save LLM tokens and execution time, the pipeline stores the latest commit SHA in `.pipeline_state.json`. On subsequent runs, it asks the GitHub API for exactly which files were modified between the previous scan and the current repository state. It passes this "changed files" list to the Tester Agent so it only writes tests for new code.

### 2. Knowledge Graph Generation (Scanner)
To strictly adhere to security policies, the code is **never cloned locally** for scanning. Instead, the Scanner triggers a GitHub Action in the cloud. The cloud workflow uses Tree-sitter to parse Python, Java, JavaScript, and TypeScript into a JSON structural graph (`kb.json`). 
- **CodeQL Integration**: The Scanner downloads the GitHub Advanced Security (CodeQL) SARIF report and physically maps the exploits to the exact AST function nodes where the vulnerabilities exist.
- **Frontend Bodies**: For frontend UI files, the scanner extracts the raw HTML/JSX tags into the Knowledge Graph so the AI can read DOM IDs for testing.

### 3. AI Test Generation (Tester)
The Tester Agent topologically sorts the graph to test deeply nested dependencies first. It analyzes the context of each function (decorators, parameters, dependencies, and CodeQL vulnerabilities) to inject a custom test strategy into the prompt.
- **Frontend / React**: Generates E2E Selenium WebDriver UI tests.
- **Backend `@RestController`**: Generates API Integration tests (RestAssured/MockMvc).
- **Vulnerable Code**: Generates specific Negative/Security regression tests to verify CodeQL patches.
