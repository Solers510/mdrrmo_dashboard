from __future__ import annotations

from sqlalchemy import select

from database.connection import SessionLocal
from database.models import SystemAuditLog


class AuditServiceError(Exception):
    """Raised when the system audit log cannot be read."""


def list_audit_entries(*, limit: int = 500) -> list[dict[str, object]]:
    safe_limit = max(1, min(int(limit), 2000))

    try:
        with SessionLocal() as session:
            statement = (
                select(SystemAuditLog)
                .order_by(
                    SystemAuditLog.occurred_at.desc(),
                    SystemAuditLog.id.desc(),
                )
                .limit(safe_limit)
            )
            entries = session.scalars(statement).all()

            return [
                {
                    "id": int(entry.id),
                    "table_name": entry.table_name,
                    "operation": entry.operation,
                    "record_id": entry.record_id,
                    "actor_snapshot": entry.actor_snapshot,
                    "old_data": entry.old_data,
                    "new_data": entry.new_data,
                    "occurred_at": entry.occurred_at,
                }
                for entry in entries
            ]

    except Exception as error:
        raise AuditServiceError(
            "The system audit log could not be loaded."
        ) from error
