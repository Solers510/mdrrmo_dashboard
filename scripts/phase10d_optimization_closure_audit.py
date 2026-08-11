from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import statistics
from time import perf_counter
import tracemalloc
from zoneinfo import ZoneInfo

from services.export_service import (
    build_excel_report,
    build_pdf_report,
)
from services.report_service import (
    get_report_snapshot,
    list_report_snapshots,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIRECTORY = PROJECT_ROOT / "performance_results"
RESULT_PATH = RESULT_DIRECTORY / "phase10d_closure_audit.json"
REPORT_PAGE = PROJECT_ROOT / "pages" / "reports.py"
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

WARMUP_RUNS = 1
MEASURED_RUNS = 5

EXPORT_ATTENTION_MS = 25.0
COMBINED_EXPORT_ATTENTION_MS = 50.0


def _measure(
    name: str,
    function,
) -> dict[str, object]:
    for _ in range(WARMUP_RUNS):
        function()

    wall_samples: list[float] = []
    peak_samples: list[float] = []
    output_sizes: list[int] = []

    for _ in range(MEASURED_RUNS):
        tracemalloc.start()
        tracemalloc.reset_peak()

        started_at = perf_counter()
        value = function()
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
        peak_samples.append(
            peak_bytes / 1024.0
        )

        if isinstance(
            value,
            (bytes, bytearray),
        ):
            output_sizes.append(
                len(value)
            )

    return {
        "name": name,
        "median_wall_ms": round(
            statistics.median(
                wall_samples
            ),
            3,
        ),
        "min_wall_ms": round(
            min(
                wall_samples
            ),
            3,
        ),
        "max_wall_ms": round(
            max(
                wall_samples
            ),
            3,
        ),
        "median_peak_kib": round(
            statistics.median(
                peak_samples
            ),
            1,
        ),
        "output_bytes": (
            int(
                statistics.median(
                    output_sizes
                )
            )
            if output_sizes
            else None
        ),
    }


def _report_page_audit(
) -> dict[str, object]:
    source = REPORT_PAGE.read_text(
        encoding="utf-8-sig"
    )

    excel_calls = source.count(
        "build_excel_report("
    )
    pdf_calls = source.count(
        "build_pdf_report("
    )
    cache_data_present = (
        "@st.cache_data"
        in source
    )

    return {
        "excel_build_calls_in_page":
            excel_calls,
        "pdf_build_calls_in_page":
            pdf_calls,
        "streamlit_data_cache_present":
            cache_data_present,
        "exports_built_during_normal_rerun":
            (
                excel_calls > 0
                and pdf_calls > 0
                and not cache_data_present
            ),
    }


def main() -> None:
    print("")
    print(
        "MDRRMO PHASE 10D OPTIMIZATION-CLOSURE AUDIT"
    )
    print("=" * 78)
    print(
        "Read-only audit: no operational-data write is performed."
    )
    print("")

    snapshots = list_report_snapshots(
        limit=1
    )

    if not snapshots:
        print(
            "No saved report snapshot exists; export benchmark skipped."
        )
        export_results: list[
            dict[str, object]
        ] = []
        selected_snapshot_id = None
    else:
        selected_snapshot_id = int(
            snapshots[0]["id"]
        )
        record = get_report_snapshot(
            snapshot_id=
                selected_snapshot_id
        )

        excel_result = _measure(
            "excel_export_build",
            lambda: build_excel_report(
                record
            ),
        )
        pdf_result = _measure(
            "pdf_export_build",
            lambda: build_pdf_report(
                record
            ),
        )
        combined_result = _measure(
            "combined_export_build",
            lambda: (
                build_excel_report(
                    record
                ),
                build_pdf_report(
                    record
                ),
            ),
        )

        export_results = [
            excel_result,
            pdf_result,
            combined_result,
        ]

        for result in export_results:
            size_text = (
                f" | output {result['output_bytes']} bytes"
                if result[
                    "output_bytes"
                ] is not None
                else ""
            )
            print(
                f"{result['name']}: "
                f"median {result['median_wall_ms']:.3f} ms | "
                f"peak {result['median_peak_kib']:.1f} KiB"
                f"{size_text}"
            )

    page_audit = _report_page_audit()

    print("")
    print(
        "STATIC RERUN AUDIT"
    )
    print("-" * 78)
    print(
        "Excel builder calls in reports page: "
        f"{page_audit['excel_build_calls_in_page']}"
    )
    print(
        "PDF builder calls in reports page: "
        f"{page_audit['pdf_build_calls_in_page']}"
    )
    print(
        "Streamlit data cache on reports page: "
        f"{page_audit['streamlit_data_cache_present']}"
    )

    findings: list[str] = []

    if (
        page_audit[
            "exports_built_during_normal_rerun"
        ]
    ):
        findings.append(
            "REPORT_EXPORT_REBUILD_ON_RERUN"
        )

    by_name = {
        str(row["name"]): row
        for row in export_results
    }

    excel = by_name.get(
        "excel_export_build"
    )
    pdf = by_name.get(
        "pdf_export_build"
    )
    combined = by_name.get(
        "combined_export_build"
    )

    if (
        excel is not None
        and float(
            excel[
                "median_wall_ms"
            ]
        )
        >= EXPORT_ATTENTION_MS
    ):
        findings.append(
            "EXCEL_EXPORT_COST_MATERIAL"
        )

    if (
        pdf is not None
        and float(
            pdf[
                "median_wall_ms"
            ]
        )
        >= EXPORT_ATTENTION_MS
    ):
        findings.append(
            "PDF_EXPORT_COST_MATERIAL"
        )

    if (
        combined is not None
        and float(
            combined[
                "median_wall_ms"
            ]
        )
        >= COMBINED_EXPORT_ATTENTION_MS
    ):
        findings.append(
            "COMBINED_EXPORT_COST_MATERIAL"
        )

    payload = {
        "schema_version": 1,
        "captured_at":
            datetime.now(
                MANILA_TIMEZONE
            ).isoformat(),
        "purpose":
            "Phase 10D optimization closure audit",
        "selected_snapshot_id":
            selected_snapshot_id,
        "warmup_runs":
            WARMUP_RUNS,
        "measured_runs":
            MEASURED_RUNS,
        "thresholds": {
            "single_export_attention_ms":
                EXPORT_ATTENTION_MS,
            "combined_export_attention_ms":
                COMBINED_EXPORT_ATTENTION_MS,
        },
        "report_page_audit":
            page_audit,
        "export_results":
            export_results,
        "findings":
            findings,
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
    if findings:
        print(
            "Optimization candidates:"
        )
        for finding in findings:
            print(
                f"- {finding}"
            )
    else:
        print(
            "No material optimization candidate was detected "
            "by this closure audit."
        )

    print("")
    print(
        f"Local result: {RESULT_PATH}"
    )
    print(
        "PHASE 10D OPTIMIZATION-CLOSURE AUDIT: PASS"
    )


if __name__ == "__main__":
    main()
