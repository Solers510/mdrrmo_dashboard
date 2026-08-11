from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.phase10_performance_baseline import (
    MEASURED_RUNS,
    WARMUP_RUNS,
    _target_functions,
    benchmark_target,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIRECTORY = PROJECT_ROOT / "performance_results"
BASELINE_PATH = RESULT_DIRECTORY / "phase10a_baseline.json"
AFTER_PATH = RESULT_DIRECTORY / "phase10b_after.json"
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

TARGET_QUERY_LIMITS = {
    "dashboard_bundle": 15,
    "population_reconciliation": 8,
}

MINIMUM_QUERY_REDUCTION = {
    "dashboard_bundle": 20,
    "population_reconciliation": 20,
}


def _by_name(
    payload: dict[str, object],
) -> dict[str, dict[str, object]]:
    return {
        str(row["name"]): row
        for row in payload["results"]
    }


def _percentage_change(
    before: float,
    after: float,
) -> float | None:
    if before == 0:
        return None
    return (
        (after - before)
        / before
    ) * 100.0


def main() -> None:
    if not BASELINE_PATH.exists():
        raise SystemExit(
            "PHASE 10B COMPARISON BLOCKED: "
            "performance_results/phase10a_baseline.json is missing."
        )

    baseline = json.loads(
        BASELINE_PATH.read_text(
            encoding="utf-8"
        )
    )
    before = _by_name(
        baseline
    )

    print("")
    print(
        "MDRRMO PHASE 10B BEFORE/AFTER PERFORMANCE CHECK"
    )
    print("=" * 80)
    print(
        f"Warmups: {WARMUP_RUNS}; measured runs: {MEASURED_RUNS}"
    )
    print("")

    after_results = []

    for name, target in _target_functions():
        print(
            f"Benchmarking {name}..."
        )
        result = benchmark_target(
            name,
            target,
        )
        after_results.append(
            result
        )

    payload = {
        "schema_version": 1,
        "captured_at":
            datetime.now(
                MANILA_TIMEZONE
            ).isoformat(),
        "purpose":
            "Phase 10B post-query-optimization benchmark",
        "baseline_file":
            BASELINE_PATH.name,
        "warmup_runs":
            WARMUP_RUNS,
        "measured_runs":
            MEASURED_RUNS,
        "results":
            after_results,
    }

    RESULT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )
    AFTER_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    after = _by_name(
        payload
    )

    failures: list[str] = []

    print("")
    print("COMPARISON")
    print("-" * 80)

    for name in before:
        if name not in after:
            continue

        before_row = before[name]
        after_row = after[name]

        before_wall = float(
            before_row["median_wall_ms"]
        )
        after_wall = float(
            after_row["median_wall_ms"]
        )
        before_queries = int(
            before_row["median_query_count"]
        )
        after_queries = int(
            after_row["median_query_count"]
        )

        wall_change = _percentage_change(
            before_wall,
            after_wall,
        )
        query_change = (
            after_queries
            - before_queries
        )

        wall_text = (
            f"{wall_change:+.1f}%"
            if wall_change is not None
            else "n/a"
        )

        print(
            f"{name}: "
            f"wall {before_wall:.3f} -> {after_wall:.3f} ms "
            f"({wall_text}); "
            f"queries {before_queries} -> {after_queries} "
            f"({query_change:+d})"
        )

        if name in TARGET_QUERY_LIMITS:
            limit = TARGET_QUERY_LIMITS[
                name
            ]
            minimum_reduction = (
                MINIMUM_QUERY_REDUCTION[
                    name
                ]
            )

            if after_queries > limit:
                failures.append(
                    f"{name}: query count {after_queries} "
                    f"exceeds target limit {limit}."
                )

            if (
                before_queries
                - after_queries
                < minimum_reduction
            ):
                failures.append(
                    f"{name}: query count reduction is "
                    f"{before_queries - after_queries}, "
                    f"expected at least {minimum_reduction}."
                )

            diagnostics = {
                str(value)
                for value in after_row.get(
                    "diagnostics",
                    [],
                )
            }

            if "N_PLUS_ONE_CANDIDATE" in diagnostics:
                failures.append(
                    f"{name}: N_PLUS_ONE_CANDIDATE remains."
                )

    print("")
    print(
        f"Post-optimization result: {AFTER_PATH}"
    )

    if failures:
        print("")
        print(
            "PHASE 10B PERFORMANCE CHECK: FAIL"
        )
        for failure in failures:
            print(
                f"- {failure}"
            )
        raise SystemExit(1)

    print("")
    print(
        "PHASE 10B PERFORMANCE CHECK: PASS"
    )
    print(
        "The targeted N+1 database pattern was measurably reduced."
    )


if __name__ == "__main__":
    main()
