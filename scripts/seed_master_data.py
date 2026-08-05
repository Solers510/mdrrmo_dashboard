from sqlalchemy import select

from database.connection import SessionLocal
from database.models import AlertLevel, Barangay


ALERT_LEVELS = [
    {
        "code": "WHITE",
        "name": "White Alert",
        "description": (
            "Operational definition pending final confirmation "
            "from current national and MDRRMO Naic policies."
        ),
        "color_hex": "#F4F4F4",
        "display_order": 1,
    },
    {
        "code": "BLUE",
        "name": "Blue Alert",
        "description": (
            "Operational definition pending final confirmation "
            "from current national and MDRRMO Naic policies."
        ),
        "color_hex": "#1F6FEB",
        "display_order": 2,
    },
    {
        "code": "RED",
        "name": "Red Alert",
        "description": (
            "Operational definition pending final confirmation "
            "from current national and MDRRMO Naic policies."
        ),
        "color_hex": "#D64545",
        "display_order": 3,
    },
]


BARANGAYS = [
    ("0402115001", "Bagong Karsada"),
    ("0402115002", "Balsahan"),
    ("0402115003", "Bancaan"),
    ("0402115004", "Bucana Malaki"),
    ("0402115005", "Bucana Sasahan"),
    ("0402115006", "Capt. C. Nazareno"),
    ("0402115007", "Calubcob"),
    ("0402115008", "Palangue 2 & 3"),
    ("0402115009", "Gomez-Zamora"),
    ("0402115010", "Halang"),
    ("0402115011", "Humbac"),
    ("0402115012", "Ibayo Estacion"),
    ("0402115013", "Ibayo Silangan"),
    ("0402115014", "Kanluran"),
    ("0402115015", "Labac"),
    ("0402115016", "Latoria"),
    ("0402115018", "Mabolo"),
    ("0402115019", "Makina"),
    ("0402115020", "Malainen Bago"),
    ("0402115021", "Malainen Luma"),
    ("0402115022", "Molino"),
    ("0402115023", "Munting Mapino"),
    ("0402115024", "Muzon"),
    ("0402115025", "Palangue 1"),
    ("0402115026", "Sabang"),
    ("0402115028", "San Roque"),
    ("0402115029", "Santulan"),
    ("0402115030", "Sapa"),
    ("0402115031", "Timalan Balsahan"),
    ("0402115032", "Timalan Concepcion"),
]


def seed_alert_levels() -> None:
    with SessionLocal() as session:
        for record in ALERT_LEVELS:
            existing = session.scalar(
                select(AlertLevel).where(
                    AlertLevel.code == record["code"]
                )
            )

            if existing is None:
                session.add(
                    AlertLevel(**record)
                )

        session.commit()


def seed_barangays() -> None:
    with SessionLocal() as session:
        for psgc_code, name in BARANGAYS:
            existing = session.scalar(
                select(Barangay).where(
                    Barangay.psgc_code == psgc_code
                )
            )

            if existing is None:
                session.add(
                    Barangay(
                        psgc_code=psgc_code,
                        name=name,
                    )
                )

        session.commit()


def main() -> None:
    seed_alert_levels()
    seed_barangays()

    print("Master data seeding completed.")


if __name__ == "__main__":
    main()