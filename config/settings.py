"""Unified settings — YAML files provide defaults; env vars take precedence.

All configuration values can be set three ways (priority: high → low):
    1. Environment variable (e.g. ``MAX_ITERATIONS=20``)
    2. Per-use-case YAML file in ``config/*.yaml``
    3. Hardcoded fallback in this file

The ``settings`` singleton exposes the same flat attribute API as before,
so existing code (``settings.MAX_ITERATIONS``, etc.) works unchanged.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

from .loader import cfg as _yaml_cfg

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=False)


def _get(path: str, default):
    """Resolve a dotted path like ``"llm.deepseek.model"`` from YAML, then env, then *default*."""
    # 1. YAML
    parts = path.split(".")
    val = _yaml_cfg
    try:
        for p in parts:
            val = val[p]
        return val
    except (KeyError, TypeError):
        pass
    return default


class Settings:
    """Flat-attribute settings object, populated from YAML + env + fallbacks."""

    # ---- LLM provider ----
    DEFAULT_PROVIDER       = os.getenv("DEFAULT_LLM_PROVIDER", _get("llm.default_provider", "deepseek"))

    # ---- DeepSeek ----
    DEEPSEEK_API_KEY       = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL      = os.getenv("DEEPSEEK_BASE_URL", _get("llm.deepseek.base_url", "https://api.deepseek.com"))
    DEEPSEEK_MODEL         = os.getenv("DEEPSEEK_MODEL", _get("llm.deepseek.model", "deepseek-chat"))

    # ---- Qwen ----
    QWEN_API_KEY           = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL          = os.getenv("QWEN_BASE_URL", _get("llm.qwen.base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    QWEN_MODEL             = os.getenv("QWEN_MODEL", _get("llm.qwen.model", "qwen-plus"))
    QWEN_VISION_MODEL      = os.getenv("QWEN_VISION_MODEL", _get("llm.qwen_vision.model", "qwen-vl-plus"))

    # ---- ReAct loop ----
    MAX_ITERATIONS         = int(os.getenv("MAX_ITERATIONS", _get("agent.react.max_iterations", 50)))
    TEMPERATURE            = float(os.getenv("TEMPERATURE", _get("llm.generation.temperature", 0.7)))
    MAX_TOKENS             = int(os.getenv("MAX_TOKENS", _get("llm.generation.max_tokens", 4096)))

    # ---- Context / memory ----
    SLIDING_WINDOW_SIZE    = int(os.getenv("SLIDING_WINDOW_SIZE", _get("agent.react.sliding_window_size", 10)))
    MAX_CONTEXT_TOKENS     = int(os.getenv("MAX_CONTEXT_TOKENS", _get("agent.react.max_context_tokens", 8000)))

    # ---- Sandbox ----
    SANDBOX_ROOT           = os.getenv("SANDBOX_ROOT", str(ROOT_DIR / _get("tools.sandbox.root_dir", "sandbox")))

    # ---- Wikipedia ----
    WIKIPEDIA_LANGUAGE     = os.getenv("WIKIPEDIA_LANGUAGE", _get("tools.wikipedia.language", "zh"))

    # ---- Multi-agent ----
    MULTI_AGENT_MAX_WORKERS = int(os.getenv("MULTI_AGENT_MAX_WORKERS", _get("tools.multi_agent.max_workers", 3)))

    # ---- Storage paths ----
    @classmethod
    def get_store_dir(cls) -> Path:
        return ROOT_DIR / _get("storage.conversation_store.store_dir", "conversations")

    @classmethod
    def get_ltm_path(cls) -> Path:
        return ROOT_DIR / _get("agent.long_term_memory.file_path", "memory/long_term.json")

    # ---- LLM config helper (unchanged API) ----
    @classmethod
    def get_llm_config(cls, provider: str | None = None) -> dict:
        provider = provider or cls.DEFAULT_PROVIDER
        if provider == "deepseek":
            return {"api_key": cls.DEEPSEEK_API_KEY, "base_url": cls.DEEPSEEK_BASE_URL, "model": cls.DEEPSEEK_MODEL}
        if provider == "qwen":
            return {"api_key": cls.QWEN_API_KEY, "base_url": cls.QWEN_BASE_URL, "model": cls.QWEN_MODEL}
        raise ValueError(f"Unknown provider: {provider}")

    # ---- Per-use-case LLM params (new API) ----
    @classmethod
    def get_use_case_params(cls, use_case: str) -> dict:
        """Return ``{temperature, max_tokens}`` for a named use case.

        *use_case* keys: planning, synthesis, memory_extraction,
        memory_compression, debate, rerank, image_description.
        """
        defaults = {"temperature": cls.TEMPERATURE, "max_tokens": cls.MAX_TOKENS}
        uc = _yaml_cfg.get("llm", {}).get("use_cases", {}).get(use_case, {})
        return {
            "temperature": uc.get("temperature", defaults["temperature"]),
            "max_tokens": uc.get("max_tokens", defaults["max_tokens"]),
        }


settings = Settings()
