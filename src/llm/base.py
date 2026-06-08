"""
Abstract base class for LLM clients.
Every provider must implement these two methods.
"""
from abc import ABC, abstractmethod
from typing import Generator

# ------------------------------------------------------------------
# Default inference parameters
# ------------------------------------------------------------------
DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_MAX_TOKENS: int = 4096


class BaseLLMClient(ABC):
    """Unified interface for all LLM providers."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stop: list[str] | None = None,
    ) -> str:
        """
        Send a chat-completion request and return the full response text.
        """
        ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stop: list[str] | None = None,
    ) -> Generator[str, None, None]:
        """
        Stream a chat-completion. Yields text chunks as they arrive.
        """
        ...
