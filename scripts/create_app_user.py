import argparse

from config.access_control import APP_ROLES
from database.connection import session_scope
from database.models import AppUser
from database.repositories import (
    fetch_app_user_by_email,
)


def normalize_email(
    value: str,
) -> str:
    email = value.strip().lower()

    if not email or "@" not in email:
        raise argparse.ArgumentTypeError(
            "Enter a valid email address."
        )

    return email


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create or update an authorized MDRRMO "
            "application user."
        )
    )

    parser.add_argument(
        "--email",
        required=True,
        type=normalize_email,
    )

    parser.add_argument(
        "--name",
        required=True,
    )

    parser.add_argument(
        "--role",
        required=True,
        choices=APP_ROLES,
    )

    arguments = parser.parse_args()

    display_name = arguments.name.strip()

    if not display_name:
        parser.error(
            "Display name cannot be empty."
        )

    with session_scope() as session:
        user = fetch_app_user_by_email(
            session,
            email=arguments.email,
        )

        if user is None:
            user = AppUser(
                email=arguments.email,
                display_name=display_name,
                role=arguments.role,
                is_active=True,
            )

            session.add(user)
            session.flush()

            action = "Created"

        else:
            user.display_name = display_name
            user.role = arguments.role
            user.is_active = True

            session.flush()

            action = "Updated"

        print(
            f"{action} application user #{user.id}: "
            f"{user.email} — {user.role}"
        )


if __name__ == "__main__":
    main()