from __future__ import annotations

from logging import Formatter, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import traceback
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIRECTORY / "mdrrmo_app.log"

LOGGER = getLogger("mdrrmo")
LOGGER.setLevel("ERROR")
LOGGER.propagate = False

_SECRET_PATTERNS = (
    (
        re.compile(
            r"(?i)(postgres(?:ql)?(?:\+\w+)?://[^:\s/@]+:)([^@\s]+)(@)"
        ),
        r"\1[REDACTED]\3",
    ),
    (
        re.compile(
            r"(?i)((?:password|client_secret|cookie_secret|token)\s*[=:]\s*)([^\s,;]+)"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(authorization:\s*bearer\s+)([^\s]+)"),
        r"\1[REDACTED]",
    ),
)


def redact_sensitive_text(value: str) -> str:
    redacted = value
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _ensure_handler() -> None:
    if LOGGER.handlers:
        return

    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    LOGGER.addHandler(handler)


def log_exception(context: str, error: BaseException) -> str:
    """Log a sanitized traceback and return a support reference."""
    _ensure_handler()

    reference = uuid4().hex[:12].upper()
    rendered = "".join(
        traceback.format_exception(
            type(error),
            error,
            error.__traceback__,
        )
    )

    LOGGER.error(
        "reference=%s | context=%s\n%s",
        reference,
        redact_sensitive_text(context),
        redact_sensitive_text(rendered),
    )

    return reference
