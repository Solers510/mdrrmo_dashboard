from collections.abc import Generator
from contextlib import contextmanager
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.runtime import (
    bounded_integer,
    deployment_mode,
    is_cloud_deployment,
    normalize_database_url,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Configure it in the local .env file or "
        "the deployment platform's protected secrets."
    )


DEPLOYMENT_MODE = deployment_mode()
IS_CLOUD_DEPLOYMENT = is_cloud_deployment()
SQLALCHEMY_DATABASE_URL = normalize_database_url(DATABASE_URL)

DB_CONNECT_TIMEOUT_SECONDS = bounded_integer(
    "DB_CONNECT_TIMEOUT_SECONDS",
    5,
    minimum=1,
    maximum=30,
)

DB_POOL_TIMEOUT_SECONDS = bounded_integer(
    "DB_POOL_TIMEOUT_SECONDS",
    5,
    minimum=1,
    maximum=10,
)

ENGINE_OPTIONS: dict[str, object] = {
    "pool_pre_ping": True,
    "pool_timeout": DB_POOL_TIMEOUT_SECONDS,
    "connect_args": {
        "connect_timeout": DB_CONNECT_TIMEOUT_SECONDS,
    },
}

if IS_CLOUD_DEPLOYMENT:
    DB_POOL_SIZE = bounded_integer(
        "DB_POOL_SIZE",
        4,
        minimum=1,
        maximum=8,
    )
    DB_MAX_OVERFLOW = bounded_integer(
        "DB_MAX_OVERFLOW",
        1,
        minimum=0,
        maximum=4,
    )
    DB_POOL_RECYCLE_SECONDS = bounded_integer(
        "DB_POOL_RECYCLE_SECONDS",
        300,
        minimum=60,
        maximum=3600,
    )
    DB_SSLMODE = str(os.getenv("DB_SSLMODE", "require")).strip().lower()

    if DB_SSLMODE in {"allow", "disable", "prefer"}:
        raise RuntimeError(
            "Cloud deployments require encrypted PostgreSQL connections. "
            "Set DB_SSLMODE to require, verify-ca, or verify-full."
        )

    ENGINE_OPTIONS.update(
        {
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "pool_recycle": DB_POOL_RECYCLE_SECONDS,
        }
    )
    ENGINE_OPTIONS["connect_args"] = {
        "connect_timeout": DB_CONNECT_TIMEOUT_SECONDS,
        "sslmode": DB_SSLMODE,
        "application_name": "mdrrmo_naic_streamlit",
    }


engine: Engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
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
