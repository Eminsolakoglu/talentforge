from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")

    is_local = "localhost" in url or "127.0.0.1" in url or "@postgres:" in url
    if not is_local and "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"

    return url


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    _normalize_database_url(settings.database_url),
    connect_args={"connect_timeout": 15},
    pool_pre_ping=True,
    poolclass=NullPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models.postgres  # noqa: F401

    Base.metadata.create_all(bind=engine)
