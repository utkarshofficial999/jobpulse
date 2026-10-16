from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from src.modules.sources.models import Source


@dataclass
class RawJobData:
    external_id: str
    payload: dict[str, Any]


class BaseConnector(ABC):
    """Abstract base connector for ATS and job board platforms."""

    @abstractmethod
    def fetch(self, source: Source) -> list[RawJobData]:
        """
        Fetches raw job postings from the given source.
        Returns a list of RawJobData containing external_id and raw payload.
        Must raise appropriate exceptions on fatal network/HTTP failures.
        """
        pass
