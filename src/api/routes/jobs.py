from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.jobs.models import Job
from src.modules.deduplication.service import DeduplicationService
from src.modules.verification.service import VerificationService
from src.modules.embeddings.service import EmbeddingService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/")
def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status: 'open' or 'closed'"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    remote_type: Optional[str] = Query(None, description="Filter by remote_type: 'remote', 'hybrid', 'onsite'"),
    seniority: Optional[str] = Query(None, description="Filter by seniority"),
    verification_status: Optional[str] = Query(None, description="Filter by verification_status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Lists canonical jobs with optional filtering."""
    stmt = select(Job).order_by(Job.first_seen_at.desc())

    if status:
        stmt = stmt.where(Job.status == status)
    if company:
        stmt = stmt.where(Job.company.ilike(f"%{company}%"))
    if remote_type:
        stmt = stmt.where(Job.remote_type == remote_type)
    if seniority:
        stmt = stmt.where(Job.seniority == seniority)
    if verification_status:
        stmt = stmt.where(Job.verification_status == verification_status)

    stmt = stmt.limit(limit).offset(offset)
    jobs = list(db.execute(stmt).scalars().all())

    return [
        {
            "id": job.id,
            "source_id": job.source_id,
            "cluster_id": job.cluster_id,
            "is_primary": job.is_primary_in_cluster,
            "external_id": job.external_id,
            "title": job.title,
            "company": job.company,
            "locations": job.locations,
            "remote_type": job.remote_type,
            "seniority": job.seniority,
            "employment_type": job.employment_type,
            "description": job.description[:300] + "..." if len(job.description) > 300 else job.description,
            "apply_url": job.apply_url,
            "posted_at": job.posted_at,
            "status": job.status,
            "verification_status": job.verification_status,
            "verified_at": job.verified_at,
            "has_embedding": job.embedding is not None,
            "first_seen_at": job.first_seen_at,
            "last_seen_at": job.last_seen_at,
            "closed_at": job.closed_at,
        }
        for job in jobs
    ]


@router.get("/search")
def search_jobs(
    q: str = Query(..., description="Natural language search query (e.g. 'Senior Python distributed systems engineer')"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Semantic vector search powered by pgvector."""
    results = EmbeddingService.search_similar_jobs(db, query=q, limit=limit)
    return [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "seniority": job.seniority,
            "remote_type": job.remote_type,
            "locations": job.locations,
            "apply_url": job.apply_url,
            "similarity_score": round(score, 4),
        }
        for job, score in results
    ]


@router.post("/deduplicate")
def trigger_deduplication(limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    """Triggers cross-source deduplication on unclustered jobs."""
    clustered = DeduplicationService.batch_deduplicate(db, limit=limit)
    return {"status": "success", "clustered_jobs": clustered}


@router.post("/verify")
def trigger_batch_verification(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    """Triggers live verification check on active jobs."""
    summary = VerificationService.batch_verify(db, limit=limit)
    return {"status": "success", "summary": summary}


@router.post("/embed")
def trigger_batch_embedding(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    """Generates pgvector embeddings for newly ingested jobs."""
    embedded = EmbeddingService.generate_batch(db, batch_size=limit)
    return {"status": "success", "embedded_jobs": embedded}
