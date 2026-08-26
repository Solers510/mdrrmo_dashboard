from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from database.connection import SessionLocal
from database.repositories import fetch_all_app_users
from scripts.phase10_performance_baseline import benchmark_target
from services.access_service import resolve_app_user


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIRECTORY = PROJECT_ROOT / "performance_results"
RESULT_PATH = RESULT_DIRECTORY / "phase10c_auth_lookup_cost.json"
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def _benchmark_email() -> str:
    with SessionLocal() as session:
        users = fetch_all_app_users(
            session
        )

        for user in users:
            if user.is_active:
                return str(
                    user.email
                ).strip().lower()

    raise RuntimeError(
        "No active application account exists for the "
        "authorization lookup benchmark."
    )


def main() -> None:
    email = _benchmark_email()

    single = benchmark_target(
        "authorization_single_lookup",
        lambda: resolve_app_user(
            email=email
        ),
    )

    duplicate = benchmark_target(
        "authorization_duplicate_lookup",
        lambda: (
            resolve_app_user(
                email=email
            ),
            resolve_app_user(
                email=email
            ),
        ),
    )

    single_queries = int(
        single[
            "median_query_count"
        ]
    )
    duplicate_queries = int(
        duplicate[
            "median_query_count"
        ]
    )

    saved_queries = (
        duplicate_queries
        - single_queries
    )

    payload = {
        "schema_version": 1,
        "captured_at":
            datetime.now(
                MANILA_TIMEZONE
            ).isoformat(),
        "purpose":
            "Phase 10C authorization lookup cost model",
        "identity_disclosed":
            False,
        "single_lookup":
            single,
        "duplicate_lookup":
            duplicate,
        "queries_saved_per_page_rerun":
            saved_queries,
    }

    RESULT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )
    RESULT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("")
    print(
        "MDRRMO PHASE 10C AUTHORIZATION LOOKUP COST"
    )
    print("=" * 76)
    print(
        "The benchmark uses an active application account "
        "without printing its identity."
    )
    print(
        "Previous rerun model: "
        f"{duplicate_queries} DB queries; "
        f"median {duplicate['median_wall_ms']:.3f} ms"
    )
    print(
        "Optimized rerun model: "
        f"{single_queries} DB query; "
        f"median {single['median_wall_ms']:.3f} ms"
    )
    print(
        f"Database queries saved per selected-page rerun: {saved_queries}"
    )
    print(
        f"Local result: {RESULT_PATH}"
    )

    if single_queries != 1:
        raise SystemExit(
            "PHASE 10C AUTHORIZATION COST CHECK: FAIL - "
            f"single lookup used {single_queries} queries."
        )

    if duplicate_queries != 2:
        raise SystemExit(
            "PHASE 10C AUTHORIZATION COST CHECK: FAIL - "
            f"duplicate lookup used {duplicate_queries} queries."
        )

    if saved_queries != 1:
        raise SystemExit(
            "PHASE 10C AUTHORIZATION COST CHECK: FAIL - "
            "expected exactly one saved authorization query."
        )

    print("")
    print(
        "PHASE 10C AUTHORIZATION COST CHECK: PASS"
    )


if __name__ == "__main__":
    main()
