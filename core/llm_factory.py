"""
core/llm_factory.py
-------------------
Multi-provider LLM factory with automatic prompt caching.

Supported providers (auto-detected from LLM_MODEL env var):
  gemini-*        -> Google Gemini  (Explicit CachedContent API before batch)
  gpt-* / o1-*   -> OpenAI         (Automatic - no code needed, >=1024 token cache)
  claude-*        -> Anthropic      (cache_control flag injected into system message)

Multi-key load balancing works for ALL providers:
  GEMINI_API_KEY,    GEMINI_API_KEY_2    ... GEMINI_API_KEY_9
  OPENAI_API_KEY,    OPENAI_API_KEY_2    ... OPENAI_API_KEY_9
  ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_2 ... ANTHROPIC_API_KEY_9

Backward compat: GEMINI_MODEL still works as alias for LLM_MODEL.

Usage:
    from core.llm_factory import create_llm, LLMBundle

    bundle = create_llm()
    bundle.setup_cache(system_prompt_text)  # call before abatch (Gemini explicit cache)
    chain  = build_chain(bundle)            # from cs_agent.py
    ...
    bundle.teardown_cache()                 # call after batch done
"""

import os
import datetime
import threading
import litellm

# ---------------------------------------------------------------------------
# Cost Tracking
# ---------------------------------------------------------------------------

_cost_log_lock = threading.Lock()
_COST_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "output", "cost_tracking.txt"
)
_key_alias_map = {}

def _build_key_alias_map() -> dict:
    mapping = {}
    for prefix in ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
        for i in range(1, 10):
            suffix = "" if i == 1 else f"_{i}"
            key = os.getenv(f"{prefix}{suffix}")
            if key:
                mapping[key] = f'{prefix.split("_")[0]} Key {i}'
    return mapping

def _track_cost_callback(kwargs, completion_response, start_time, end_time):
    try:
        usage = completion_response.get("usage", {})
        input_tokens  = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        cost = litellm.completion_cost(completion_response=completion_response)
        cost = cost or 0.0

        model     = completion_response.get("model", "unknown")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        api_key   = kwargs.get("litellm_params", {}).get("api_key", "")
        key_alias = _key_alias_map.get(api_key, "Unknown Key")

        phase    = getattr(litellm, "current_phase", "Unknown")
        log_line = (
            f"[{timestamp}] [{phase}] Model: {model} ({key_alias}) | "
            f"Tokens: {input_tokens} In, {output_tokens} Out | "
            f"Cost: ${cost:.6f}\n"
        )

        os.makedirs(os.path.dirname(_COST_LOG_FILE), exist_ok=True)

        with _cost_log_lock:
            with open(_COST_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
    except Exception as exc:
        print(f"[WARN] Failed to track cost: {exc}")

# Register cost tracking callback
litellm.success_callback = [_track_cost_callback]
litellm._async_success_callback = [_track_cost_callback]
_key_alias_map = _build_key_alias_map()

from dataclasses import dataclass, field

from typing import Any, Optional



# -- LLMBundle -----------------------------------------------------------------

@dataclass
class LLMBundle:
    """
    Returned by create_llm().
    Holds the LangChain LLM, provider metadata, and cache lifecycle hooks.
    """
    llm:      Any   # LangChain BaseChatModel - .with_structured_output() + .abatch() ready
    provider: str   # "gemini" | "openai" | "anthropic" | "unknown"
    model:    str   # raw model name from .env, e.g. "gemini-2.5-flash-lite"

    _cache_obj: Any = field(default=None, repr=False)

    def setup_cache(self, system_prompt_text: str, ttl_minutes: int = 60) -> None:
        """
        Creates a Gemini server-side context cache for the static system prompt.
        Call ONCE before starting abatch() for the FRD run.

        Gemini   -> creates explicit CachedContent (shared across all TC calls)
        OpenAI   -> auto-caches repeated prefixes >=1024 tokens (50% discount, no code needed)
        Anthropic -> cache_control already injected in build_chain() (90% saving)
        """
        if self.provider == "openai":
            print("[CACHE] OpenAI auto-caches repeated prompts >=1024 tokens (50% discount).")
            return
        if self.provider == "anthropic":
            print("[CACHE] Anthropic cache_control set in system message (~90% saving on cached tokens).")
            return
        if self.provider != "gemini":
            return

        try:
            import google.generativeai as genai
        except ImportError:
            print("[CACHE] WARNING: google-generativeai not installed - skipping explicit cache.")
            print("        Run: pip install google-generativeai")
            return

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[CACHE] WARNING: GEMINI_API_KEY not set - skipping explicit cache.")
            return

        genai.configure(api_key=api_key)
        try:
            self._cache_obj = genai.caching.CachedContent.create(
                model=f"models/{self.model}",
                system_instruction=system_prompt_text,
                ttl=datetime.timedelta(minutes=ttl_minutes),
            )
            print(f"[CACHE] OK Gemini cache created: {self._cache_obj.name} (TTL={ttl_minutes}min)")
        except Exception as exc:
            print(f"[CACHE] WARNING: Failed to create Gemini cache ({exc}) - running without cache.")
            self._cache_obj = None

    def teardown_cache(self) -> None:
        """
        Deletes the Gemini context cache after the batch run completes.
        Prevents unnecessary storage costs. No-op for OpenAI / Anthropic.
        """
        if self._cache_obj is None:
            return
        try:
            self._cache_obj.delete()
            print(f"[CACHE] Gemini cache deleted: {self._cache_obj.name}")
        except Exception as exc:
            print(f"[CACHE] WARNING: Failed to delete cache ({exc}) - it will expire on its own.")
        finally:
            self._cache_obj = None

    @property
    def gemini_cache_name(self) -> Optional[str]:
        """Returns Gemini cache resource name, or None if no cache is active."""
        return getattr(self._cache_obj, "name", None)


# -- Helpers -------------------------------------------------------------------

def _collect_keys(env_prefix: str) -> list:
    """
    Reads PREFIX, PREFIX_2 ... PREFIX_9 from env vars.
    Returns list of all non-empty values found.
    """
    keys = []
    for i in range(1, 10):
        suffix = "" if i == 1 else f"_{i}"
        key = os.getenv(f"{env_prefix}{suffix}")
        if key:
            keys.append(key)
    return keys


def _build_litellm_router(model_name: str, keys: list, rpm: int, tpm: int) -> Any:
    """
    Builds a ChatLiteLLMRouter with one LiteLLM Router deployment per API key.
    LiteLLM handles round-robin / least-busy routing and auto-retries on 429.
    """
    try:
        from litellm import Router
        from langchain_litellm import ChatLiteLLMRouter
    except ImportError as exc:
        raise ImportError(
            f"Missing dependency: {exc}\n"
            "Run: pip install langchain-litellm litellm"
        ) from exc

    model_list = [
        {
            "model_name": model_name,
            "litellm_params": {
                "model":   model_name,
                "api_key": key,
                "rpm":     rpm,
                "tpm":     tpm,
            },
        }
        for key in keys
    ]

    router = Router(
        model_list=model_list,
        num_retries=5,                   # auto-retry on 429 / transient errors
        retry_after=5,                   # seconds between retries
        routing_strategy="least-busy",   # route to key with fewest in-flight requests
        cooldown_time=5,                 # short cooldown so single keys recover quickly
        allowed_fails=10,                # tolerate transient rate limits
        timeout=120,
    )

    return ChatLiteLLMRouter(
        router=router,
        model_name=model_name,
        temperature=0.2,
    )


# -- Provider-specific builders ------------------------------------------------

def _build_gemini(model: str) -> Any:
    keys = _collect_keys("GEMINI_API_KEY")
    if not keys:
        raise RuntimeError(
            "\n[ERROR] No GEMINI_API_KEY found.\n"
            "  Add to .env:\n"
            "    GEMINI_API_KEY=your_key_here\n"
        )
    rpm = int(os.getenv("GEMINI_RPM", "50"))
    tpm = int(os.getenv("GEMINI_TPM", "4000000"))
    litellm_model = f"gemini/{model}"
    print(
        f"[LLM] Gemini - model={litellm_model}, "
        f"keys={len(keys)}, rpm={rpm}/key, tpm={tpm}/key"
    )
    return _build_litellm_router(litellm_model, keys, rpm, tpm)


def _build_openai(model: str) -> Any:
    keys = _collect_keys("OPENAI_API_KEY")
    if not keys:
        raise RuntimeError(
            "\n[ERROR] No OPENAI_API_KEY found.\n"
            "  Add to .env:\n"
            "    OPENAI_API_KEY=sk-...\n"
            "    OPENAI_API_KEY_2=sk-...  # optional, for multi-key load balancing\n"
        )
    rpm = int(os.getenv("OPENAI_RPM", "500"))
    tpm = int(os.getenv("OPENAI_TPM", "2000000"))
    print(
        f"[LLM] OpenAI - model={model}, "
        f"keys={len(keys)}, rpm={rpm}/key"
    )
    return _build_litellm_router(model, keys, rpm, tpm)


def _build_anthropic(model: str) -> Any:
    keys = _collect_keys("ANTHROPIC_API_KEY")
    if not keys:
        raise RuntimeError(
            "\n[ERROR] No ANTHROPIC_API_KEY found.\n"
            "  Add to .env:\n"
            "    ANTHROPIC_API_KEY=sk-ant-...\n"
            "    ANTHROPIC_API_KEY_2=sk-ant-...  # optional, for multi-key load balancing\n"
        )
    rpm = int(os.getenv("ANTHROPIC_RPM", "50"))
    tpm = int(os.getenv("ANTHROPIC_TPM", "2000000"))
    litellm_model = f"anthropic/{model}"
    print(
        f"[LLM] Anthropic - model={litellm_model}, "
        f"keys={len(keys)}, rpm={rpm}/key"
    )
    return _build_litellm_router(litellm_model, keys, rpm, tpm)


# -- Public factory ------------------------------------------------------------

def create_llm() -> LLMBundle:
    """
    Reads LLM_MODEL (or GEMINI_MODEL for backward compat) from .env,
    detects provider from model name prefix, returns an LLMBundle.

    Provider detection rules:
        gemini-*              -> Google Gemini (Explicit CachedContent API)
        gpt-* / o1-* / o3-*  -> OpenAI        (Automatic cache >= 1024 tokens)
        claude-*              -> Anthropic      (cache_control in system message)

    Raises RuntimeError with a clear message if required env vars are missing.
    """
    model = os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"

    m = model.lower()

    if m.startswith("gemini"):
        return LLMBundle(llm=_build_gemini(model), provider="gemini", model=model)

    if any(m.startswith(p) for p in ("gpt-", "o1-", "o3-", "o4-")):
        return LLMBundle(llm=_build_openai(model), provider="openai", model=model)

    if m.startswith("claude"):
        return LLMBundle(llm=_build_anthropic(model), provider="anthropic", model=model)

    # Unknown prefix - attempt best-effort via whichever keys are available
    print(f"[LLM] WARNING: Unknown model prefix '{model}' - attempting via LiteLLM directly.")
    keys = (
        _collect_keys("OPENAI_API_KEY")
        or _collect_keys("GEMINI_API_KEY")
        or _collect_keys("ANTHROPIC_API_KEY")
    )
    if not keys:
        raise RuntimeError(
            f"[ERROR] No API keys found for unknown model '{model}'.\n"
            "  Set one of: OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY in .env"
        )
    llm = _build_litellm_router(model, keys, rpm=50, tpm=2000000)
    return LLMBundle(llm=llm, provider="unknown", model=model)
