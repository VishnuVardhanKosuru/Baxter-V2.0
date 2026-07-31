# Knowledge Graph Schema Documentation

This document outlines the exact metadata extracted by the `extract_ast.py` Tree-sitter script and merged by `kb_merger.py`. 

The final `kb.json` is a pure structural Knowledge Graph consisting of **Nodes** and **Edges**. Note that the raw source code body is intentionally **not** extracted to keep the data lean and secure.

---

## 1. Nodes
There are three types of nodes extracted from the AST: `FILE`, `CLASS`, and `FUNCTION`.

### File Nodes
Represents a physical file in the repository.
*   **id**: Unique identifier (e.g., `file://src/main.py`)
*   **type**: `FILE`
*   **name**: The basename of the file (e.g., `main.py`)
*   **properties**:
    *   **language**: The programming language detected (e.g., `python`, `java`)
    *   **size_bytes**: The size of the file.
    *   **vulnerabilities**: (Optional) List of CodeQL SARIF findings attached to this file.

### Class Nodes
Represents a class definition.
*   **id**: Unique identifier (e.g., `class://src/main.py/Database`)
*   **type**: `CLASS`
*   **name**: The name of the class (e.g., `Database`)
*   **file**: The relative path to the file it belongs to.
*   **line_start**: The line number where the class begins.
*   **line_end**: The line number where the class ends.
*   **properties**:
    *   **vulnerabilities**: (Optional) CodeQL findings attached specifically to this class.

### Function / Method Nodes
Represents a function or a method inside a class. This contains the richest metadata for the Testing Agent.
*   **id**: Unique identifier (e.g., `func://src/main.py/connect`)
*   **type**: `FUNCTION`
*   **name**: The name of the function (e.g., `connect`)
*   **file**: The relative path to the file it belongs to.
*   **line_start**: The line number where the function begins.
*   **line_end**: The line number where the function ends.
*   **parameters**: A list of arguments the function takes (e.g., `["self", "host", "port"]`).
*   **docstring**: The first block comment inside the function. Extremely important as it provides the semantic "intent" of the function for the LLM since the raw code body is hidden (e.g., `"Connects to the SQL database."`).
*   **decorators**: Any annotations or decorators applied to the function (e.g., `["@app.route('/login')", "@pytest.fixture"]`).
*   **properties**:
    *   **vulnerabilities**: (Optional) CodeQL findings attached specifically to this function.

---

## 2. Edges (Relationships)
Edges connect the nodes together to form the dependency graph.

### `DEFINES`
*   **Source**: `FILE`
*   **Target**: `FUNCTION` or `CLASS`
*   **Meaning**: The file contains the definition of this function or class.

### `CONTAINS`
*   **Source**: `CLASS`
*   **Target**: `FUNCTION`
*   **Meaning**: The class contains this method.

### `CALLS`
*   **Source**: `FUNCTION` (The Caller)
*   **Target**: `FUNCTION` (The Callee)
*   **Meaning**: The source function executes the target function inside its body. 
*   *Note: This is the most critical edge for the Testing Agent, as it determines the "blast radius" and dependency order for bottom-up test generation.*
