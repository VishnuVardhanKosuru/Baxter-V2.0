# Incremental Agent Walkthrough

The `incremental_agent.py` script is officially complete and ready for action! It completely automates the process of generating tests for only the exact functions that a developer just pushed, without rewriting your entire test suite!

## How it works under the hood
1. **GitHub API Patch:** It uses your local `GITHUB_PAT` to fetch the specific commit diff.
2. **Deterministic Delta Parsing:** It uses regular expressions to find every `+` line (newly modified/added lines) inside the diff patch. It doesn't use AI to guess this—it's pure math.
3. **Graph Intersection:** It grabs your new `kb.json` file. If a function's `line_start` and `line_end` overlaps with any of the modified line numbers in the diff, that function is mathematically proven to be affected.
4. **Privacy Generation:** It fetches the target source code *only* for Leaf node functions, temporarily holds it in RAM, sends it to Gemini for generation, and then instantly wipes it.
5. **Subfolder Saving:** It drops the generated Java files neatly into `positive/`, `bva/`, and `negative/` subfolders, and appends the new manual tests directly to your CSVs!

## How to use it!
Whenever there is a new push on your repository, simply grab the latest commit SHA (e.g., `a1b2c3d4e5f6`) and run:

```bash
python agents/incremental_agent.py --commit a1b2c3d4e5f6
```

That's it! It will instantly print out exactly which functions were modified and queue them up for generation!
