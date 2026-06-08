"""
DeepSeek API client — OpenAI-compatible protocol.
"""
from typing import Generator
from openai import OpenAI

from .base import BaseLLMClient, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS


class DeepSeekClient(BaseLLMClient):
    """Client for the DeepSeek chat-completion API."""

    def __init__(self, api_key: str, base_url: str, model: str):
        super().__init__(api_key, base_url, model)
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stop: list[str] | None = None,
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )
        return resp.choices[0].message.content or ""

    # ------------------------------------------------------------------
    def stream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stop: list[str] | None = None,
    ) -> Generator[str, None, None]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
