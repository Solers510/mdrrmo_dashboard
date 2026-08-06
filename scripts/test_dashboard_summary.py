from services.dashboard_service import (
    get_dashboard_bundle,
)


def main() -> None:
    dashboard = get_dashboard_bundle()

    active_event = dashboard["active_event"]

    if active_event is None:
        print("No active event exists.")
        return

    provisional = dashboard[
        "provisional_summary"
    ]

    official = dashboard[
        "official_summary"
    ]

    print(
        f"Active event: "
        f"{active_event['event_name']}"
    )

    print("\nProvisional summary:")
    print(provisional)

    print("\nOfficial summary:")
    print(official)


if __name__ == "__main__":
    main()