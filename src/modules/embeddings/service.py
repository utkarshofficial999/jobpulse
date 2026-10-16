from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.modules.jobs.models import Job
from src.modules.embeddings.base import BaseEmbeddingProvider
from src.modules.embeddings.local import FastEmbedProvider

_default_provider: Optional[BaseEmbeddingProvider] = None


def get_embedding_provider() -> BaseEmbeddingProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = FastEmbedProvider()
    return _default_provider


def format_job_for_embedding(job: Job) -> str:
    """Creates a dense, structured text representation optimized for semantic vector retrieval."""
    locations = ", ".join(job.locations) if job.locations else "Not specified"
    desc_sample = " ".join(job.description.split()[:150])  # approx 150 words

    return (
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Seniority: {job.seniority}\n"
        f"Workplace: {job.remote_type}\n"
        f"Locations: {locations}\n"
        f"Employment: {job.employment_type}\n"
        f"Summary: {desc_sample}"
    )


class EmbeddingService:
    """Service to generate and persist pgvector embeddings for canonical jobs."""

    @classmethod
    def generate_batch(
        cls,
        db: Session,
        batch_size: int = 50,
        provider: Optional[BaseEmbeddingProvider] = None,
    ) -> int:
        """
        Embeds un-embedded open jobs in batches.
        """
        provider = provider or get_embedding_provider()

        stmt = (
            select(Job)
            .where(Job.status == "open", Job.embedded_at.is_(None))
            .limit(batch_size)
        )
        jobs = list(db.execute(stmt).scalars().all())

        if not jobs:
            return 0

        texts = [format_job_for_embedding(job) for job in jobs]
        vectors = provider.embed_texts(texts)

        now = datetime.now(timezone.utc)
        for job, vector in zip(jobs, vectors):
            job.embedding = vector
            job.embedded_at = now

        db.commit()
        logger.info(
            "Generated vector embeddings for jobs",
            count=len(jobs),
            dimension=provider.dimension,
        )
        return len(jobs)

    @classmethod
    def search_similar_jobs(
        cls,
        db: Session,
        query: str,
        limit: int = 10,
        provider: Optional[BaseEmbeddingProvider] = None,
    ) -> list[tuple[Job, float]]:
        """
        Performs semantic vector search across canonical jobs.
        Returns list of (Job, similarity_score).
        """
        provider = provider or get_embedding_provider()
        query_vector = provider.embed_texts([query])[0]

        # Check if running against Postgres with pgvector
        if db.bind and db.bind.dialect.name == "postgresql":
            # pgvector cosine distance operator (<=>)
            stmt = (
                select(Job, Job.embedding.cosine_distance(query_vector).label("distance"))
                .where(Job.status == "open", Job.embedding.isnot(None))
                .order_by("distance")
                .limit(limit)
            )
            results = db.execute(stmt).all()
            # Convert cosine distance (0 to 2) to cosine similarity (1 - distance)
            return [(row[0], float(1.0 - row[1])) for row in results]

        # SQLite/in-memory fallback for unit testing: compute in Python
        stmt = select(Job).where(Job.status == "open", Job.embedding.isnot(None)).limit(100)
        jobs = list(db.execute(stmt).scalars().all())

        import numpy as np
        qv = np.array(query_vector)
        qv_norm = np.linalg.norm(qv)

        scored = []
        for j in jobs:
            if j.embedding:
                jv = np.array(j.embedding)
                denom = qv_norm * np.linalg.norm(jv)
                sim = float(np.dot(qv, jv) / denom) if denom > 0 else 0.0
                scored.append((j, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]
