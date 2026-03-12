"""Abstract SocialPoster interface."""

from abc import ABC, abstractmethod


class SocialPoster(ABC):
    """Base class for all social media posting targets."""

    @abstractmethod
    def post(self, copy: dict, post: dict, db_row=None):
        """Post *copy* for a WordPress *post*. Returns a result identifier or None."""
        ...

    @abstractmethod
    def check_auth(self) -> tuple[bool, str]:
        """Verify credentials with a lightweight API call.
        Returns (ok, message) — never raises.
        """
        ...

    @property
    @abstractmethod
    def platform(self) -> str:
        """Machine-readable platform name, e.g. 'linkedin'."""
        ...
