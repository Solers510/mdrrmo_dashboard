from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re

_LOGGER_ROOT_NAME = "mdrrmo"
_LOG_FILE_NAME = "mdrrmo_app.log"
_SECRET_KEY_MARKERS = (
    "PASSWORD", "PASSWD", "SECRET", "TOKEN",
    "DATABASE_URL", "CLIENT_SECRET", "COOKIE_SECRET", "API_KEY",
)

def _sensitive_values() -> tuple[str, ...]:
    values = []
    for key, value in os.environ.items():
        if value and any(marker in key.upper() for marker in _SECRET_KEY_MARKERS):
            values.append(value)
    return tuple(sorted(set(values), key=len, reverse=True))

def sanitize_log_text(text: str) -> str:
    sanitized = str(text)
    for value in _sensitive_values():
        if len(value) >= 4:
            sanitized = sanitized.replace(value, "[REDACTED]")
    sanitized = re.sub(
        r"(?i)(password\s*=\s*)[^\s,;]+",
        r"\1[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)((?:postgres|postgresql)(?:\+[^:]+)?://[^:\s/@]+:)[^@\s/]+(@)",
        r"\1[REDACTED]\2",
        sanitized,
    )
    return sanitized

class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return sanitize_log_text(super().format(record))

def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def get_app_log_path() -> Path:
    return _project_root() / "logs" / _LOG_FILE_NAME

def _configure_root_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_ROOT_NAME)
    if getattr(logger, "_mdrrmo_configured", False):
        return logger
    log_path = get_app_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(
        RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    setattr(logger, "_mdrrmo_configured", True)
    return logger

def get_app_logger(component: str) -> logging.Logger:
    return _configure_root_logger().getChild(component)
