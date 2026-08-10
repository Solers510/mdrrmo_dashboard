from collections.abc import Generator
from contextlib import contextmanager
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Add it to the .env file."
    )


DB_CONNECT_TIMEOUT_SECONDS = max(
    int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
    1,
)

DB_POOL_TIMEOUT_SECONDS = max(
    int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "5")),
    1,
)

ENGINE_OPTIONS: dict[str, object] = {
    "pool_pre_ping": True,
    "pool_timeout": DB_POOL_TIMEOUT_SECONDS,
    "connect_args": {
        "connect_timeout": DB_CONNECT_TIMEOUT_SECONDS,
    },
}


engine: Engine = create_engine(
    DATABASE_URL,
    **ENGINE_OPTIONS,
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a database session that automatically commits,
    rolls back on failure, and closes afterward.
    """
    session = SessionLocal()

    try:
        yield session
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()