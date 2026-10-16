from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from src.config import settings
from src.core.logging import logger


def get_engine():
    db_url = settings.DATABASE_URL
    # In development, check if PostgreSQL is reachable within 1s; if not, fallback to sqlite
    if "postgresql" in db_url and settings.APP_ENV == "development":
        try:
            test_engine = create_engine(db_url, connect_args={"connect_timeout": 1})
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return test_engine
        except Exception:
            fallback = "sqlite:///./pulseai.db"
            logger.warning(
                "PostgreSQL not running locally. Using SQLite for instant development",
                url=fallback,
            )
            return create_engine(fallback, connect_args={"check_same_thread": False})

    return create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


engine = get_engine()

SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
)

Base = declarative_base()


def import_all_models():
    """Ensure all SQLAlchemy models are registered in the Base metadata registry."""
    import src.modules.sources.models  # noqa: F401
    import src.modules.jobs.models  # noqa: F401
    import src.modules.deduplication.models  # noqa: F401
    import src.modules.users.models  # noqa: F401
    import src.modules.matching.models  # noqa: F401
    import src.modules.notifications.models  # noqa: F401


def get_db():
    """Dependency for API requests or task workers."""
    import_all_models()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for standalone scripts and Celery tasks."""
    import_all_models()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

