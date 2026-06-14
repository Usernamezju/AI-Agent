"""YAML configuration loader — loads all .yaml files from the config directory.

Usage::

    from config.loader import cfg
    print(cfg["llm"]["deepseek"]["model"])          # deepseek-chat
    print(cfg["agent"]["react"]["max_iterations"])  # 15
    print(cfg["tools"]["code_interpreter"])          # {...}

Environment variables can override any leaf value using the pattern
``SECTION_KEY_SUBKEY`` (uppercase, dot-separated path joined by ``_``)::

    export AGENT_REACT_MAX_ITERATIONS=30
    export TOOLS_CODE_INTERPRETER_DEFAULT_TIMEOUT_SEC=20

Keys in the YAML files that differ from defaults set via env vars will
be noted at import time (via ``logging.info``, not printed silently).
"""
from __future__ import annotations
import os
import yaml
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).resolve().parent


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*.  Lists are replaced, not merged."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _apply_env_overrides(cfg: dict, prefix: str = "") -> None:
    """Walk *cfg* and override leaf values from matching environment variables.

    An env var named ``LLM_DEEPSEEK_MODEL`` overrides ``cfg["llm"]["deepseek"]["model"]``.
    """
    for key, value in cfg.items():
        full_key = f"{prefix}_{key}".upper() if prefix else key.upper()
        if isinstance(value, dict):
            _apply_env_overrides(value, full_key)
        else:
            env_val = os.environ.get(full_key)
            if env_val is not None:
                # Cast to the original type
                if isinstance(value, bool):
                    cfg[key] = env_val.lower() in ("1", "true", "yes")
                elif isinstance(value, int):
                    cfg[key] = int(env_val)
                elif isinstance(value, float):
                    cfg[key] = float(env_val)
                elif isinstance(value, list):
                    cfg[key] = [x.strip() for x in env_val.split(",") if x.strip()]
                else:
                    cfg[key] = env_val


def load_all_configs() -> dict[str, Any]:
    """Load and merge all ``.yaml`` files from the config directory.

    Returns a nested dict keyed by file stem (e.g. ``"llm"``, ``"agent"``).
    Environment variables take final precedence.
    """
    merged: dict[str, Any] = {}

    for yaml_path in sorted(_CONFIG_DIR.glob("*.yaml")):
        stem = yaml_path.stem  # e.g. "llm", "agent"
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if stem in merged:
            _deep_merge(merged[stem], data)
        else:
            merged[stem] = data

    _apply_env_overrides(merged)
    return merged


# Singleton — loaded once at import time
cfg: dict[str, Any] = load_all_configs()


def reload() -> dict[str, Any]:
    """Force a full reload of all YAML configs (useful in tests)."""
    global cfg
    cfg = load_all_configs()
    return cfg
