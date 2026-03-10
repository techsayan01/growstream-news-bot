"""Abstract Pipeline base class."""

from abc import ABC, abstractmethod

from sites.base import SiteConfig


class Pipeline(ABC):
    """Base class for all content pipelines."""

    def __init__(self, site: SiteConfig):
        self.site = site

    @abstractmethod
    def run(self) -> None:
        """Execute the pipeline end-to-end."""
        ...
