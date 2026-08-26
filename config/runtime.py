from __future__ import annotations

import os
from collections.abc import Mapping


LOCAL_DEPLOYMENT = "local"
CLOUD_DEPLOYMENT = "cloud"
SUPPORTED_DEPLOYMENT_MODES = frozenset(
    {
        LOCAL_DEPLOYMENT,
        CLOUD_DEPLOYMENT,
    }
)


def deployment_mode(environ: Mapping[str, str] | None = None) -> str:
    """Return the validated application deployment mode."""
    source = os.environ if environ is None else environ
    value = str(
        source.get("APP_DEPLOYMENT_MODE", LOCAL_DEPLOYMENT)
    ).strip().lower()

    if value not in SUPPORTED_DEPLOYMENT_MODES:
        supported = ", ".join(sorted(SUPPORTED_DEPLOYMENT_MODES))
        raise RuntimeError(
            "APP_DEPLOYMENT_MODE must be one of: " + supported + "."
        )

    return value


def is_cloud_deployment(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the application is using the cloud pilot profile."""
    return deployment_mode(environ) == CLOUD_DEPLOYMENT


def normalize_database_url(value: str) -> str:
    """Use the installed psycopg 3 driver for common PostgreSQL URLs."""
    database_url = str(value or "").strip()

    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix(
            "postgres://"
        )

    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix(
            "postgresql://"
        )

    return database_url


def bounded_integer(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Read a bounded integer setting with a clear configuration error."""
    source = os.environ if environ is None else environ
    raw_value = str(source.get(name, default)).strip()

    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error

    if not minimum <= value <= maximum:
        raise RuntimeError(
            f"{name} must be between {minimum} and {maximum}."
        )

    return value
