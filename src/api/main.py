from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.core.logging import setup_logging, logger
from src.core.database import SessionLocal, Base, engine
from src.api.routes import sources, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured logging
    setup_logging()
    logger.info("Initializing Pulse AI API server")

    # In development / local testing, auto-create tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified")
    except Exception as e:
        logger.warning("Could not auto-create tables on startup (Postgres might be initializing)", error=str(e))

    yield
    logger.info("Shutting down Pulse AI API server")


app = FastAPI(
    title="Pulse AI - Job Discovery & Alert Engine",
    description="Modular monolith job ingestion, normalization, deduplication, and alerting service.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.routes import sources, jobs, users

# Mount routes
app.include_router(sources.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.get("/health")
def health_check():
    """Health check for DB connectivity."""
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error("Health check DB error", error=str(e))
    finally:
        db.close()

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }
