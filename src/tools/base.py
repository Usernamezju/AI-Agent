"""Abstract base class for all tools."""
from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Every tool must expose name, description, JSON-Schema parameters, and a run() method."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict: ...

    @abstractmethod
    def run(self, **kwargs) -> str: ...
