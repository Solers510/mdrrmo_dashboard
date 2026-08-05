from sqlalchemy import text

from database.connection import engine


def main() -> None:
    query = text("""
        SELECT
            current_database() AS database_name,
            current_user AS database_user,
            current_setting('TimeZone') AS timezone,
            NOW() AS current_time
    """)

    with engine.connect() as connection:
        result = connection.execute(query).mappings().one()

    print("Database connection successful.")
    print(f"Database: {result['database_name']}")
    print(f"User: {result['database_user']}")
    print(f"Timezone: {result['timezone']}")
    print(f"Current time: {result['current_time']}")


if __name__ == "__main__":
    main()