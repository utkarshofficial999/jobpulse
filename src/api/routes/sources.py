from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.sources.models import Source
from src.modules.sources.schemas import SourceCreate, SourceRead
from src.modules.sources.repository import SourceRepository
from src.modules.discovery.service import crawl_source

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.post("/", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    """Registers a new job board source for crawling."""
    source = SourceRepository.create(
        db=db,
        name=payload.name,
        connector_type=payload.connector_type,
        config=payload.config,
        poll_interval_seconds=payload.poll_interval_seconds,
    )
    return source


@router.get("/", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    """Lists all registered job sources."""
    stmt = select(Source).order_by(Source.created_at.desc())
    return list(db.execute(stmt).scalars().all())


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: str, db: Session = Depends(get_db)):
    """Gets details of a single source."""
    source = SourceRepository.get_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/{source_id}/crawl")
def trigger_crawl(source_id: str, db: Session = Depends(get_db)):
    """Manually triggers an immediate crawl for the given source."""
    source = SourceRepository.get_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        metrics = crawl_source(source_id=source.id, db=db)
        return {
            "status": "success",
            "metrics": metrics.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {str(e)}")
