"""
core/llm_factory.py
-------------------
Multi-provider LLM factory with automatic prompt caching and cost tracking.

Supported providers (auto-detected from the LLM_MODEL env var):
  gemini-*        -> Google Gemini  (explicit CachedContent API before batch)
  gpt-* / o1-*    -> OpenAI         (automatic prefix cache, >=1024 tokens)
  claude-*        -> Anthropic      (cache_control flag injected in system message)

Multi-key load balancing works for ALL providers:
  GEMINI_API_KEY,    GEMINI_API_KEY_2    ... GEMINI_API_KEY_9
  OPENAI_API_KEY,    OPENAI_API_KEY_2    ... OPENAI_API_KEY_9
  ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_2 ... ANTHROPIC_API_KEY_9

Backward compat: GEMINI_MODEL still works as an alias for LLM_MODEL.

Usage:
    from core.llm_factory import create_llm

    bundle = create_llm()
    bundle.setup_cache(system_prompt_text)  # before abatch (Gemini explicit cache)
    chain  = build_chain(bundle)            # from agents/cs_agent.py
    ...
    bundle.teardown_cache()                 # after the batch completes
"""

import datetime
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

import litellm

from core import constants as const
from core.logger import logger

# ---------------------------------------------------------------------------
# Cost Tracking
# ---------------------------------------------------------------------------

_cost_log_lock = threading.Lock()
_cost_log_dir_ready = False
_key_alias_map: dict = {}


def _build_key_alias_map() -> dict:
    """
    Maps each configured secret key to a human-readable alias.

    Pre-computed once so the per-call cost callback resolves aliases with an O(1)
    dict lookup instead of re-reading environment variables on every LLM call.
    """
    mapping = {}
    for prefix in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        for i in range(1, const.MAX_API_KEY_SLOTS + 1):
            suffix = "" if i == 1 else f"_{i}"
            key = os.getenv(f"{prefix}{suffix}")
            if key:
                mapping[key] = f'{prefix.split("_")[0]} Key {i}'
    return mapping


def refresh_key_alias_map() -> None:
    """Rebuilds the alias map after the configured key set changes at runtime."""
    global _key_alias_map
    _key_alias_map = _build_key_alias_map()


def _track_cost_callback(kwargs, completion_response, start_time, end_time):
    """
    LiteLLM success callback — appends one cost line per completed LLM call.

    Writes only aggregate metadata (model, key alias, token counts, cost). The
    secret key itself is never logged; it is resolved to an alias first.
    Must never raise: an exception here would surface inside LiteLLM's callback
    machinery on an otherwise successful request.
    """
    global _cost_log_dir_ready
    try:
        usage = completion_response.get("usage", {}) or {}
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        try:
            cost = litellm.completion_cost(completion_response=completion_response) or 0.0
        except Exception:
            # Unknown/custom model with no pricing entry — log the call at $0
            # rather than losing the token counts entirely.
            cost = 0.0

        model = completion_response.get("model", "unknown")
        timestamp = datetime.datetime.now().strftime(const.LOG_DATE_FORMAT)

        api_key = (kwargs.get("litellm_params") or {}).get("api_key", "")
        key_alias = _key_alias_map.get(api_key, "Unknown Key")

        phase = getattr(litellm, "current_phase", "Unknown")
        log_line = (
            f"[{timestamp}] [{phase}] Model: {model} ({key_alias}) | "
            f"Tokens: {input_tokens} In, {output_tokens} Out | "
            f"Cost: ${cost:.6f}\n"
        )

        with _cost_log_lock:
            if not _cost_log_dir_ready:
                const.FILE_COST_LOG.parent.mkdir(parents=True, exist_ok=True)
                _cost_log_dir_ready = True
            with open(const.FILE_COST_LOG, "a", encoding="utf-8") as f:
                f.write(log_line)
    except Exception as exc:
        logger.warning("Failed to track LLM cost: %s", exc)


# Register cost tracking for both sync and async completions.
litellm.success_callback = [_track_cost_callback]
litellm._async_success_callback = [_track_cost_callback]
refresh_key_alias_map()


# -- LLMBundle -----------------------------------------------------------------

@dataclass
class LLMBundle:
    """
    Returned by create_llm().
    Holds the LangChain LLM, provider metadata, and cache lifecycle hooks.
    """
    llm:      Any   # LangChain BaseChatModel — .with_structured_output() + .abatch() ready
    provider: str   # "gemini" | "openai" | "anthropic" | "unknown"
    model:    str   # raw model name from .env, e.g. "gemini-3.1-flash-lite"

    _cache_obj: Any = field(default=None, repr=False)

    def setup_cache(self, system_prompt_text: str, ttl_minutes: Optional[int] = None) -> None:
        """
        Creates a Gemini server-side context cache for the static system prompt.
        Call ONCE before starting abatch() for an FRD run.

        Gemini    -> creates explicit CachedContent (shared across all TC calls)
        OpenAI    -> no-op; auto-caches repeated prefixes >=1024 tokens
        Anthropic -> no-op; cache_control is injected in build_chain()

        Never raises — a cache failure degrades to running without a cache.
        """
        if self.provider == "openai":
            logger.info("[CACHE] OpenAI auto-caches repeated prompts >=1024 tokens (50%% discount).")
            return
        if self.provider == "anthropic":
            logger.info("[CACHE] Anthropic cache_control set in system message (~90%% saving).")
            return
        if self.provider != "gemini":
            return

        ttl = ttl_minutes if ttl_minutes is not None else const.LLM_CACHE_TTL_MINUTES

        try:
            import google.generativeai as genai
        except ImportError:
            logger.warning(
                "[CACHE] google-generativeai not installed — skipping explicit cache. "
                "Install it with: pip install google-generativeai"
            )
            return

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("[CACHE] GEMINI_API_KEY not set — skipping explicit cache.")
            return

        try:
            genai.configure(api_key=api_key)
            self._cache_obj = genai.caching.CachedContent.create(
                model=f"models/{self.model}",
                system_instruction=system_prompt_text,
                ttl=datetime.timedelta(minutes=ttl),
            )
            logger.info("[CACHE] Gemini cache created: %s (TTL=%dmin)", self._cache_obj.name, ttl)
        except Exception as exc:
            logger.warning("[CACHE] Could not create Gemini cache (%s) — running without cache.", exc)
            self._cache_obj = None

    def teardown_cache(self) -> None:
        """
        Deletes the Gemini context cache after the batch run completes, to avoid
        paying for idle cache storage. No-op for OpenAI / Anthropic.
        """
        if self._cache_obj is None:
            return
        try:
            self._cache_obj.delete()
            logger.info("[CACHE] Gemini cache deleted: %s", self._cache_obj.name)
        except Exception as exc:
            logger.warning("[CACHE] Could not delete cache (%s) — it will expire on its own.", exc)
        finally:
            self._cache_obj = None

    @property
    def gemini_cache_name(self) -> Optional[str]:
        """Returns the Gemini cache resource name, or None if no cache is active."""
        return getattr(self._cache_obj, "name", None)


# -- Helpers -------------------------------------------------------------------

def collect_keys(env_prefix: str) -> list:
    """
    Reads PREFIX, PREFIX_2 ... PREFIX_N from the environment.

    N is MAX_API_KEY_SLOTS — the same bound used by the alias map and the UI key
    injector, so a key written to a slot beyond it can never be silently ignored.

    Returns:
        List of all non-empty key values found, in slot order.
    """
    keys = []
    for i in range(1, const.MAX_API_KEY_SLOTS + 1):
        suffix = "" if i == 1 else f"_{i}"
        key = os.getenv(f"{env_prefix}{suffix}")
        if key:
            keys.append(key)
    return keys


def _build_litellm_router(model_name: str, keys: list, rpm: int, tpm: int) -> Any:
    """
    Builds a ChatLiteLLMRouter with one LiteLLM Router deployment per API key.

    The router owns retry and timeout behaviour for every provider: it retries
    429s and transient network errors, applies a per-request timeout, and routes
    each call to the key with the fewest in-flight requests.
    """
    try:
        from litellm import Router
        from langchain_litellm import ChatLiteLLMRouter
    except ImportError as exc:
        raise ImportError(
            f"Missing dependency: {exc}\nRun: pip install langchain-litellm litellm"
        ) from exc

    model_list = [
        {
            "model_name": model_name,
            "litellm_params": {
                "model":   model_name,
                "api_key": key,
                "rpm":     rpm,
                "tpm":     tpm,
                "timeout": const.LLM_TIMEOUT_S,
            },
        }
        for key in keys
    ]

    router = Router(
        model_list=model_list,
        num_retries=const.LLM_ROUTER_RETRIES,
        retry_after=const.LLM_RETRY_AFTER_S,
        routing_strategy="least-busy",
        cooldown_time=const.LLM_COOLDOWN_S,
        allowed_fails=const.LLM_ALLOWED_FAILS,
        timeout=const.LLM_TIMEOUT_S,
    )

    return ChatLiteLLMRouter(
        router=router,
        model_name=model_name,
        temperature=const.LLM_TEMPERATURE,
    )


def _build_for_provider(provider: str, model: str, litellm_model: str) -> Any:
    """
    Builds the router for a known provider, reading its rate limits from env.

    Raises:
        RuntimeError: if no API key is configured for the provider.
    """
    rpm_env, tpm_env, key_prefix, default_rpm, default_tpm = const.PROVIDER_ENV_MAP[provider]

    keys = collect_keys(key_prefix)
    if not keys:
        raise RuntimeError(
            f"No {key_prefix} found for model '{model}'.\n"
            f"  Add to .env:\n"
            f"    {key_prefix}=your_key_here\n"
            f"    {key_prefix}_2=...  # optional, for multi-key load balancing"
        )

    rpm = const.env_int(rpm_env, default_rpm)
    tpm = const.env_int(tpm_env, default_tpm)

    logger.info(
        "[LLM] %s — model=%s, keys=%d, rpm=%d/key, tpm=%d/key",
        provider.capitalize(), litellm_model, len(keys), rpm, tpm,
    )
    return _build_litellm_router(litellm_model, keys, rpm, tpm)


# -- Public factory ------------------------------------------------------------

def create_llm() -> LLMBundle:
    """
    Builds an LLMBundle from LLM_MODEL (or GEMINI_MODEL for backward compat).

    Provider detection rules:
        gemini-*             -> Google Gemini (explicit CachedContent API)
        gpt-* / o1-* / o3-*  -> OpenAI        (automatic cache >=1024 tokens)
        claude-*             -> Anthropic     (cache_control in system message)

    Raises:
        RuntimeError: if no API key is configured for the detected provider.
        ImportError:  if the LiteLLM/LangChain integration is not installed.
    """
    model = os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL") or const.AVAILABLE_MODELS[0]
    m = model.lower()

    if m.startswith("gemini"):
        return LLMBundle(
            llm=_build_for_provider("gemini", model, f"gemini/{model}"),
            provider="gemini",
            model=model,
        )

    if any(m.startswith(p) for p in ("gpt-", "o1-", "o3-", "o4-")):
        return LLMBundle(
            llm=_build_for_provider("openai", model, model),
            provider="openai",
            model=model,
        )

    if m.startswith("claude"):
        return LLMBundle(
            llm=_build_for_provider("anthropic", model, f"anthropic/{model}"),
            provider="anthropic",
            model=model,
        )

    # Unknown prefix — best effort via whichever provider keys exist.
    logger.warning("[LLM] Unknown model prefix '%s' — attempting via LiteLLM directly.", model)
    keys = (
        collect_keys("OPENAI_API_KEY")
        or collect_keys("GEMINI_API_KEY")
        or collect_keys("ANTHROPIC_API_KEY")
    )
    if not keys:
        raise RuntimeError(
            f"No API keys found for unknown model '{model}'.\n"
            "  Set one of OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY in .env"
        )

    llm = _build_litellm_router(model, keys, rpm=const.env_int("GEMINI_RPM", 50), tpm=2000000)
    return LLMBundle(llm=llm, provider="unknown", model=model)
