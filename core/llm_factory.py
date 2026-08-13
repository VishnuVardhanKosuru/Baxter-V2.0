"""
core/llm_factory.py
───────────────────
Creates a real LiteLLM-backed LangChain LLM using the official
`langchain-litellm` package (ChatLiteLLMRouter).

What it does:
  - Reads GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3 (up to 9) from .env
  - Creates one LiteLLM Router deployment per key (round-robin load balancing)
  - Wraps it in ChatLiteLLMRouter — a full LangChain BaseChatModel
  - Supports .with_structured_output(), .abatch(), .ainvoke() natively
  - LiteLLM Router auto-retries on 429 / transient errors (no manual sleep)
  - Per-key RPM/TPM rate limits enforced by LiteLLM internally

Package required:
    pip install langchain-litellm

Usage:
    from core.llm_factory import create_llm

    llm   = create_llm()                                        # one shared instance
    chain = UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)
    # chain.abatch([...], config={"max_concurrency": 50})
"""

import os
from dotenv import load_dotenv

load_dotenv()


def create_llm():
    """
    Builds a ChatLiteLLMRouter with one LiteLLM Router deployment per API key.

    Key discovery order:
        GEMINI_API_KEY   → deployment 1  (primary)
        GEMINI_API_KEY_2 → deployment 2
        GEMINI_API_KEY_3 → deployment 3
        ...up to GEMINI_API_KEY_9

    Returns:
        ChatLiteLLMRouter — drop-in LangChain LLM with multi-key LiteLLM routing.
        Fully compatible with .with_structured_output() and .abatch().
    """
    try:
        from litellm import Router
        from langchain_litellm import ChatLiteLLMRouter
    except ImportError as exc:
        raise ImportError(
            f"Missing dependency: {exc}\n"
            "Run: pip install langchain-litellm litellm"
        ) from exc

    # ── Collect all configured API keys ──────────────────────────────────────
    keys = []
    for i in range(1, 10):
        suffix = "" if i == 1 else f"_{i}"
        key = os.getenv(f"GEMINI_API_KEY{suffix}")
        if key:
            keys.append(key)

    if not keys:
        raise RuntimeError(
            "\n[ERROR] No GEMINI_API_KEY found.\n"
            "  Add at least one key to your .env:\n"
            "    GEMINI_API_KEY=your_key_here\n"
        )

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    rpm        = int(os.getenv("GEMINI_RPM", "50"))
    tpm        = int(os.getenv("GEMINI_TPM", "4000000"))

    print(
        f"[LLM] LiteLLM Router — model=gemini/{model_name}, "
        f"keys={len(keys)}, rpm={rpm}/key, tpm={tpm}/key"
    )

    # ── One Router deployment per key (LiteLLM does round-robin by default) ──
    model_list = [
        {
            "model_name": f"gemini/{model_name}",      # logical name used by the chain
            "litellm_params": {
                "model":   f"gemini/{model_name}",
                "api_key": key,
                "rpm":     rpm,
                "tpm":     tpm,
            },
        }
        for key in keys
    ]

    # ── Create LiteLLM Router ─────────────────────────────────────────────────
    router = Router(
        model_list=model_list,
        num_retries=5,                      # auto-retry on 429 / network errors
        retry_after=10,                     # seconds between retries
        routing_strategy="least-busy",      # route to key with fewest in-flight requests
    )

    # ── Wrap in LangChain-compatible ChatLiteLLMRouter ────────────────────────
    return ChatLiteLLMRouter(
        router=router,
        model_name=f"gemini/{model_name}",  # which model_name from model_list to call
        temperature=0.2,
    )
