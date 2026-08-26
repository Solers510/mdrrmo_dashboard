from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import statistics
from time import perf_counter
import tracemalloc
from typing import Callable, Iterator
from zoneinfo import ZoneInfo

from sqlalchemy import event

from database.connection import engine
from services.dashboard_service import get_dashboard_bundle
from services.report_service import list_report_snapshots
from services.validation_service import (
    get_barangay_validation_queue,
    get_evacuation_validation_queue,
    get_population_reconciliation_queue,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIRECTORY = PROJECT_ROOT / "performance_results"
RESULT_PATH = RESULT_DIRECTORY / "phase10a_baseline.json"
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

WARMUP_RUNS = 1
MEASURED_RUNS = 5

HIGH_QUERY_COUNT = 20
N_PLUS_ONE_REPEAT = 5
SLOW_OPERATION_MS = 500.0


@dataclass
class QueryRecord:
    duration_ms: float
    fingerprint: str
    preview: str


class QueryCollector:
    def __init__(self) -> None:
        self.records: list[QueryRecord] = []

    def clear(self) -> None:
        self.records.clear()

    def before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        stack = conn.info.setdefault(
            "_phase10_query_start",
            [],
        )
        stack.append(perf_counter())

    def after_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        stack = conn.info.get(
            "_phase10_query_start",
            [],
        )
        started_at = (
            stack.pop()
            if stack
            else perf_counter()
        )
        elapsed_ms = (
            perf_counter()
            - started_at
        ) * 1000.0

        normalized = normalize_sql(
            str(statement)
        )
        self.records.append(
            QueryRecord(
                duration_ms=elapsed_ms,
                fingerprint=sql_fingerprint(
                    normalized
                ),
                preview=normalized[:220],
            )
        )


def normalize_sql(statement: str) -> str:
    compact = re.sub(
        r"\s+",
        " ",
        statement,
    ).strip()

    # Remove quoted literal contents and standalone numeric literals from
    # diagnostic previews. Bound parameter values are never included by the
    # SQLAlchemy event, but this keeps the artifact safe even for literal SQL.
    compact = re.sub(
        r"'(?:''|[^'])*'",
        "'?'",
        compact,
    )
    compact = re.sub(
        r"\b\d+(?:\.\d+)?\b",
        "?",
        compact,
    )

    return compact


def sql_fingerprint(
    normalized_statement: str,
) -> str:
    return sha256(
        normalized_statement.encode(
            "utf-8"
        )
    ).hexdigest()[:12]


@contextmanager
def collect_queries(
    collector: QueryCollector,
) -> Iterator[None]:
    event.listen(
        engine,
        "before_cursor_execute",
        collector.before_cursor_execute,
    )
    event.listen(
        engine,
        "after_cursor_execute",
        collector.after_cursor_execute,
    )

    try:
        yield
    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            collector.before_cursor_execute,
        )
        event.remove(
            engine,
            "after_cursor_execute",
            collector.after_cursor_execute,
        )


def _target_functions(
) -> list[tuple[str, Callable[[], object]]]:
    return [
        (
            "dashboard_bundle",
            get_dashboard_bundle,
        ),
        (
            "population_reconciliation",
            get_population_reconciliation_queue,
        ),
        (
            "barangay_validation_queue",
            get_barangay_validation_queue,
        ),
        (
            "evacuation_validation_queue",
            get_evacuation_validation_queue,
        ),
        (
            "report_history_100",
            lambda: list_report_snapshots(
                limit=100
            ),
        ),
    ]


def _query_summary(
    records: list[QueryRecord],
) -> list[dict[str, object]]:
    counts = Counter(
        record.fingerprint
        for record in records
    )

    duration_by_fingerprint: dict[
        str,
        float,
    ] = {}
    preview_by_fingerprint: dict[
        str,
        str,
    ] = {}

    for record in records:
        duration_by_fingerprint[
            record.fingerprint
        ] = (
            duration_by_fingerprint.get(
                record.fingerprint,
                0.0,
            )
            + record.duration_ms
        )
        preview_by_fingerprint.setdefault(
            record.fingerprint,
            record.preview,
        )

    ordered = sorted(
        counts,
        key=lambda fingerprint: (
            counts[fingerprint],
            duration_by_fingerprint[
                fingerprint
            ],
        ),
        reverse=True,
    )

    return [
        {
            "fingerprint":
                fingerprint,
            "count":
                counts[fingerprint],
            "total_db_ms":
                round(
                    duration_by_fingerprint[
                        fingerprint
                    ],
                    3,
                ),
            "preview":
                preview_by_fingerprint[
                    fingerprint
                ],
        }
        for fingerprint in ordered[:10]
    ]


def _diagnostics(
    *,
    median_wall_ms: float,
    median_query_count: float,
    representative_queries:
        list[dict[str, object]],
) -> list[str]:
    findings: list[str] = []

    if (
        median_query_count
        >= HIGH_QUERY_COUNT
    ):
        findings.append(
            "HIGH_QUERY_COUNT"
        )

    if (
        median_wall_ms
        >= SLOW_OPERATION_MS
    ):
        findings.append(
            "SLOW_OPERATION"
        )

    if any(
        int(row["count"])
        >= N_PLUS_ONE_REPEAT
        for row in representative_queries
    ):
        findings.append(
            "N_PLUS_ONE_CANDIDATE"
        )

    return findings


def benchmark_target(
    name: str,
    target: Callable[[], object],
) -> dict[str, object]:
    collector = QueryCollector()

    for _ in range(
        WARMUP_RUNS
    ):
        target()

    wall_samples: list[float] = []
    db_samples: list[float] = []
    query_samples: list[int] = []
    peak_kib_samples: list[float] = []
    representative_records: list[
        QueryRecord
    ] = []
    result_kind = ""

    with collect_queries(
        collector
    ):
        for _ in range(
            MEASURED_RUNS
        ):
            collector.clear()

            tracemalloc.start()
            tracemalloc.reset_peak()

            started_at = perf_counter()
            value = target()
            wall_ms = (
                perf_counter()
                - started_at
            ) * 1000.0

            _current, peak_bytes = (
                tracemalloc.get_traced_memory()
            )
            tracemalloc.stop()

            wall_samples.append(
                wall_ms
            )
            db_samples.append(
                sum(
                    record.duration_ms
                    for record
                    in collector.records
                )
            )
            query_samples.append(
                len(
                    collector.records
                )
            )
            peak_kib_samples.append(
                peak_bytes
                / 1024.0
            )
            representative_records = list(
                collector.records
            )

            if isinstance(
                value,
                dict,
            ):
                result_kind = "dict"
            elif isinstance(
                value,
                list,
            ):
                result_kind = (
                    f"list[{len(value)}]"
                )
            else:
                result_kind = type(
                    value
                ).__name__

    representative_queries = (
        _query_summary(
            representative_records
        )
    )

    median_wall_ms = (
        statistics.median(
            wall_samples
        )
    )
    median_db_ms = (
        statistics.median(
            db_samples
        )
    )
    median_query_count = (
        statistics.median(
            query_samples
        )
    )

    return {
        "name": name,
        "result_kind":
            result_kind,
        "runs":
            MEASURED_RUNS,
        "median_wall_ms":
            round(
                median_wall_ms,
                3,
            ),
        "min_wall_ms":
            round(
                min(
                    wall_samples
                ),
                3,
            ),
        "max_wall_ms":
            round(
                max(
                    wall_samples
                ),
                3,
            ),
        "median_db_ms":
            round(
                median_db_ms,
                3,
            ),
        "median_query_count":
            median_query_count,
        "max_query_count":
            max(
                query_samples
            ),
        "median_peak_kib":
            round(
                statistics.median(
                    peak_kib_samples
                ),
                1,
            ),
        "diagnostics":
            _diagnostics(
                median_wall_ms=
                    median_wall_ms,
                median_query_count=
                    median_query_count,
                representative_queries=
                    representative_queries,
            ),
        "representative_query_shapes":
            representative_queries,
    }


def main() -> None:
    results = []

    print("")
    print(
        "MDRRMO PHASE 10A PERFORMANCE BASELINE"
    )
    print("=" * 76)
    print(
        f"Warmups: {WARMUP_RUNS}; measured runs: {MEASURED_RUNS}"
    )
    print(
        "Read-only benchmark: no operational-data writes are performed."
    )
    print("")

    for name, target in (
        _target_functions()
    ):
        print(
            f"Benchmarking {name}..."
        )
        result = benchmark_target(
            name,
            target,
        )
        results.append(
            result
        )

        diagnostic_text = (
            ", ".join(
                result[
                    "diagnostics"
                ]
            )
            if result[
                "diagnostics"
            ]
            else "none"
        )

        print(
            "  median "
            f"{result['median_wall_ms']:.3f} ms | "
            f"DB {result['median_db_ms']:.3f} ms | "
            f"queries {result['median_query_count']} | "
            f"peak {result['median_peak_kib']:.1f} KiB | "
            f"diagnostics: {diagnostic_text}"
        )

        repeated = [
            row
            for row in result[
                "representative_query_shapes"
            ]
            if int(
                row["count"]
            )
            >= N_PLUS_ONE_REPEAT
        ]

        for row in repeated[:3]:
            print(
                "    repeated query: "
                f"{row['count']}x "
                f"[{row['fingerprint']}] "
                f"{row['preview'][:130]}"
            )

    payload = {
        "schema_version": 1,
        "captured_at":
            datetime.now(
                MANILA_TIMEZONE
            ).isoformat(),
        "purpose":
            "Phase 10A pre-optimization baseline",
        "warmup_runs":
            WARMUP_RUNS,
        "measured_runs":
            MEASURED_RUNS,
        "thresholds": {
            "high_query_count":
                HIGH_QUERY_COUNT,
            "n_plus_one_repeat":
                N_PLUS_ONE_REPEAT,
            "slow_operation_ms":
                SLOW_OPERATION_MS,
        },
        "results": results,
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
        "BASELINE CAPTURE: PASS"
    )
    print(
        f"Local result: {RESULT_PATH}"
    )
    print(
        "Diagnostic flags identify optimization candidates; "
        "they are not test failures."
    )


if __name__ == "__main__":
    main()
