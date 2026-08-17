"""
agents package — pipeline stages that own or execute an LLM prompt.

  doc_parser   Stage 1: .docx extraction, requirement mapping, enrichment
  cs_agent     Stage 2: Cucumber + Selenium generation
  frd_worker   Stage 2 parallel executor (abatch over one FRD's test cases)
  jira_agent   Jira ingestion and attachment classification

Deliberately re-exports nothing. Importing any submodule pulls in the LiteLLM and
LangChain stack (~985 modules), so eager re-exports here made `import agents`
cost seconds even for callers that only needed the lightweight Jira client.
Import the submodule you need directly:

    from agents.doc_parser import parse_documents
"""
