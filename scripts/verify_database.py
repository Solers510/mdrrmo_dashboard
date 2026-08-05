from sqlalchemy import func, select

from database.connection import SessionLocal
from database.models import AlertLevel, Barangay


def main() -> None:
    with SessionLocal() as session:
        alert_count = session.scalar(
            select(func.count(AlertLevel.id))
        )

        barangay_count = session.scalar(
            select(func.count(Barangay.id))
        )

    print(f"Alert levels: {alert_count}")
    print(f"Barangays: {barangay_count}")

    if alert_count != 3:
        raise RuntimeError(
            "Expected exactly 3 alert levels."
        )

    if barangay_count != 30:
        raise RuntimeError(
            "Expected exactly 30 Naic barangays."
        )

    print("Database verification passed.")


if __name__ == "__main__":
    main()