from typing import Optional
from src.core.logging import logger
from src.modules.embeddings.base import BaseEmbeddingProvider


class FastEmbedProvider(BaseEmbeddingProvider):
    """
    Local, zero-cost ONNX-based embedding provider using FastEmbed.
    Default model: 'sentence-transformers/all-MiniLM-L6-v2' (384 dimensions).
    """

    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSION = 384

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            logger.info("Initializing FastEmbed embedding model", model=self.model_name)
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        # FastEmbed returns a generator of numpy arrays
        embeddings_generator = model.embed(texts)
        return [embedding.tolist() for embedding in embeddings_generator]

    @property
    def dimension(self) -> int:
        return self.DIMENSION
