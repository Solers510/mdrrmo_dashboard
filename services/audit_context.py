from __future__ import annotations

from sqlalchemy import text


def set_audit_actor(
    session,
    *,
    user_id: int,
    display_name: str,
    role: str,
) -> None:
    """Set a transaction-local actor for PostgreSQL audit triggers."""
    actor = f"{display_name} - {role} [user_id={user_id}]"

    session.execute(
        text(
            "SELECT set_config('mdrrmo.actor', :actor, true)"
        ),
        {"actor": actor},
    )
