from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract interface for text embedding models."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates embedding vectors for a batch of strings."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the dimensionality of the generated vectors."""
        pass
