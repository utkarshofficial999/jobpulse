from src.modules.jobs.models import Job
from src.modules.embeddings.service import format_job_for_embedding
from src.modules.embeddings.base import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        # Deterministic 384-dimensional vector based on text length
        vectors = []
        for text in texts:
            val = float(len(text) % 10) / 10.0
            vec = [val] * 384
            vectors.append(vec)
        return vectors

    @property
    def dimension(self) -> int:
        return 384


def test_format_job_for_embedding():
    job = Job(
        title="Staff ML Platform Engineer",
        company="Stripe",
        seniority="staff",
        remote_type="remote",
        locations=["San Francisco, CA", "Remote - US"],
        employment_type="full_time",
        description="Design GPU training clusters and inference gateways at scale.",
        apply_url="https://stripe.com/apply/1",
    )

    formatted = format_job_for_embedding(job)
    assert "Title: Staff ML Platform Engineer" in formatted
    assert "Company: Stripe" in formatted
    assert "Workplace: remote" in formatted
    assert "Locations: San Francisco, CA, Remote - US" in formatted
    assert "GPU training clusters" in formatted


def test_mock_embedding_provider_dimension():
    provider = MockEmbeddingProvider()
    assert provider.dimension == 384

    vectors = provider.embed_texts(["hello world", "software engineer"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
