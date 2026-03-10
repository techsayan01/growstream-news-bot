"""Abstract Publisher interface."""

from abc import ABC, abstractmethod


class Publisher(ABC):
    """Base class for all publishing targets."""

    @abstractmethod
    def publish(self, title: str, html_content: str, **kwargs) -> str | None:
        """Publish a post. Returns the live URL or None on failure."""
        ...

    @abstractmethod
    def article_exists(self, query: str) -> bool:
        """Check if a post matching *query* already exists."""
        ...
