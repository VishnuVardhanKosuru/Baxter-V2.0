# Incremental Push Testing: Implementation Plan (Final)

## Goal
To generate test cases exclusively for newly pushed code (modified or added functions) without re-testing the entire repository, using a deterministic local pipeline that ensures absolute data privacy.

## Architecture (Local & In-Memory Execution)

Since test files are not committed back to the remote repository and we strictly avoid placing API keys in the cloud, this pipeline will run entirely on your local machine. **Crucially, the target repository's source code is never cloned or saved to your local disk.**

### Step 1: The New Graph
When a push happens, your existing GitHub Action automatically runs and generates a fresh `kb.json` that represents the new state of the repository. You will download this graph to your local `output/` folder.

### Step 2: Deterministic Delta Detection (No AI Parsing)
You run `python incremental_tester.py` locally. The script will:
1. Call the GitHub API (`GET /repos/{owner}/{repo}/commits/{sha}`) using your local `GITHUB_PAT` to fetch the exact `patch` of the latest push.
2. Mathematically parse the `patch` string to extract the exact line numbers that were added or modified in each file.
3. Cross-reference those line numbers against your local `kb.json` graph. 
   * *If the changed line numbers fall inside the mathematically defined `[line_start, line_end]` of a `FUNCTION` node, that function is immediately flagged as **MODIFIED** or **ADDED**.*

### Step 3: Privacy-First Test Generation
We now have a precise list of exactly which function IDs were affected by the push. We pass only these functions to Gemini 3.5 Flash Lite using your local `.env` key.

**Data Privacy Rules:**
1. **Unit Tests:** The script will JIT (Just-In-Time) fetch the raw source code from GitHub directly into your RAM. Gemini uses this string to generate the White-Box tests. As soon as generation is complete, the RAM is cleared. The code never touches your hard drive.
2. **Integration / UI Tests:** The script **will not** fetch the source code at all. It will operate strictly as a Black-Box tester, sending only the AST metadata (parameters, decorators, out-edges) from `kb.json` to Gemini.

### Step 4: Sub-Folder Organization
The new tests securely overwrite the old tests in your local Java subfolders (`positive/`, `bva/`, `negative/`), and the manual test cases are dynamically appended to your local Master CSVs.

## User Review Required
> [!IMPORTANT]
> **Approval Checklist:**
> - [x] Local execution only (No GitHub Secrets)
> - [x] Deterministic diff parsing (No LLM diff hallucination)
> - [x] 100% In-Memory Code fetching (No repo cloning)
> - [x] Strictly Black-Box for Integration tests
> 
> If everything looks perfect, approve this plan and I will start coding!
