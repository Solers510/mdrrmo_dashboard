from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import statistics
from time import perf_counter
from zoneinfo import ZoneInfo

from services.export_service import (
    build_excel_report,
    build_pdf_report,
)
from services.report_service import (
    get_report_snapshot,
    list_report_snapshots,
)
from utils.report_export_cache import (
    get_report_export_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIRECTORY = PROJECT_ROOT / "performance_results"
PHASE10D_PATH = (
    RESULT_DIRECTORY
    / "phase10d_closure_audit.json"
)
RESULT_PATH = (
    RESULT_DIRECTORY
    / "phase10e_export_cache.json"
)
MANILA_TIMEZONE = ZoneInfo(
    "Asia/Manila"
)

CACHE_HIT_RUNS = 1000
MAX_CACHE_HIT_MS = 1.0
MAX_BASELINE_FRACTION = 0.10


def _phase10d_combined_ms() -> float:
    if not PHASE10D_PATH.exists():
        raise RuntimeError(
            "Phase 10D closure result is missing."
        )

    payload = json.loads(
        PHASE10D_PATH.read_text(
            encoding="utf-8"
        )
    )

    for row in payload.get(
        "export_results",
        [],
    ):
        if (
            row.get("name")
            == "combined_export_build"
        ):
            return float(
                row["median_wall_ms"]
            )

    raise RuntimeError(
        "Phase 10D combined export benchmark is missing."
    )


def _latest_snapshot(
) -> dict[str, object]:
    rows = list_report_snapshots(
        limit=1
    )

    if not rows:
        raise RuntimeError(
            "No report snapshot exists for the Phase 10E benchmark."
        )

    return get_report_snapshot(
        snapshot_id=int(
            rows[0]["id"]
        )
    )


def main() -> None:
    baseline_ms = (
        _phase10d_combined_ms()
    )
    record = _latest_snapshot()

    build_counts = {
        "excel": 0,
        "pdf": 0,
    }

    def counted_excel(
        snapshot: dict[str, object],
    ) -> bytes:
        build_counts["excel"] += 1
        return build_excel_report(
            snapshot
        )

    def counted_pdf(
        snapshot: dict[str, object],
    ) -> bytes:
        build_counts["pdf"] += 1
        return build_pdf_report(
            snapshot
        )

    state: dict[str, object] = {}

    cold_started = perf_counter()
    first_bundle = (
        get_report_export_bundle(
            record,
            state,
            excel_builder=counted_excel,
            pdf_builder=counted_pdf,
        )
    )
    cold_ms = (
        perf_counter()
        - cold_started
    ) * 1000.0

    cache_hit_samples: list[
        float
    ] = []

    for _ in range(
        CACHE_HIT_RUNS
    ):
        started = perf_counter()
        bundle = (
            get_report_export_bundle(
                record,
                state,
                excel_builder=counted_excel,
                pdf_builder=counted_pdf,
            )
        )
        cache_hit_samples.append(
            (
                perf_counter()
                - started
            ) * 1000.0
        )

        if bundle is not first_bundle:
            raise RuntimeError(
                "The same snapshot did not reuse its cached bundle."
            )

    median_hit_ms = (
        statistics.median(
            cache_hit_samples
        )
    )
    p95_hit_ms = sorted(
        cache_hit_samples
    )[
        int(
            len(
                cache_hit_samples
            )
            * 0.95
        )
        - 1
    ]

    baseline_fraction = (
        median_hit_ms
        / baseline_ms
        if baseline_ms > 0
        else 0.0
    )

    payload = {
        "schema_version": 1,
        "captured_at":
            datetime.now(
                MANILA_TIMEZONE
            ).isoformat(),
        "purpose":
            "Phase 10E report export rerun optimization",
        "snapshot_identity_disclosed":
            False,
        "phase10d_combined_export_median_ms":
            round(
                baseline_ms,
                3,
            ),
        "phase10e_cold_build_ms":
            round(
                cold_ms,
                3,
            ),
        "phase10e_cache_hit_median_ms":
            round(
                median_hit_ms,
                6,
            ),
        "phase10e_cache_hit_p95_ms":
            round(
                p95_hit_ms,
                6,
            ),
        "cache_hit_runs":
            CACHE_HIT_RUNS,
        "excel_build_count":
            build_counts[
                "excel"
            ],
        "pdf_build_count":
            build_counts[
                "pdf"
            ],
        "cache_hit_fraction_of_phase10d":
            round(
                baseline_fraction,
                6,
            ),
        "excel_output_bytes":
            len(
                first_bundle.excel_bytes
            ),
        "pdf_output_bytes":
            len(
                first_bundle.pdf_bytes
            ),
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
        "MDRRMO PHASE 10E REPORT EXPORT CACHE BENCHMARK"
    )
    print("=" * 80)
    print(
        "Phase 10D combined eager export median: "
        f"{baseline_ms:.3f} ms"
    )
    print(
        "Phase 10E first build: "
        f"{cold_ms:.3f} ms"
    )
    print(
        "Phase 10E same-snapshot cache-hit median: "
        f"{median_hit_ms:.6f} ms"
    )
    print(
        "Phase 10E same-snapshot cache-hit p95: "
        f"{p95_hit_ms:.6f} ms"
    )
    print(
        "Builder calls across first build + "
        f"{CACHE_HIT_RUNS} cache hits: "
        f"Excel={build_counts['excel']}, "
        f"PDF={build_counts['pdf']}"
    )
    print(
        "Cache-hit cost as fraction of Phase 10D eager cost: "
        f"{baseline_fraction * 100.0:.4f}%"
    )
    print(
        f"Local result: {RESULT_PATH}"
    )

    failures: list[str] = []

    if (
        build_counts["excel"]
        != 1
    ):
        failures.append(
            "Excel builder ran more than once."
        )

    if (
        build_counts["pdf"]
        != 1
    ):
        failures.append(
            "PDF builder ran more than once."
        )

    if (
        median_hit_ms
        > MAX_CACHE_HIT_MS
    ):
        failures.append(
            "Median cache-hit time exceeded "
            f"{MAX_CACHE_HIT_MS:.3f} ms."
        )

    if (
        baseline_fraction
        > MAX_BASELINE_FRACTION
    ):
        failures.append(
            "Cache-hit cost exceeded 10% of "
            "the Phase 10D eager-build baseline."
        )

    if failures:
        print("")
        print(
            "PHASE 10E EXPORT CACHE CHECK: FAIL"
        )
        for failure in failures:
            print(
                f"- {failure}"
            )
        raise SystemExit(1)

    print("")
    print(
        "PHASE 10E EXPORT CACHE CHECK: PASS"
    )
    print(
        "Repeated reruns reuse the same per-session export bytes."
    )


if __name__ == "__main__":
    main()
