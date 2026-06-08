from abc import ABC, abstractmethod
from typing import Generator


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
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ) -> str:
        ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ) -> Generator[str, None, None]:
        ...
