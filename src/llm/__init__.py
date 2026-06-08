"""
Factory that returns the correct LLM client based on provider name.
"""
from config.settings import settings
from .base import BaseLLMClient
from .deepseek_client import DeepSeekClient


def create_llm_client(provider: str | None = None) -> BaseLLMClient:
    provider = provider or settings.DEFAULT_PROVIDER
    cfg = settings.get_llm_config(provider)

    if provider == "deepseek":
        return DeepSeekClient(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            model=cfg["model"],
        )

    # Qwen uses the same OpenAI-compatible protocol
    if provider == "qwen":
        return DeepSeekClient(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            model=cfg["model"],
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
