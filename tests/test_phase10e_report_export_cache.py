from __future__ import annotations

from pathlib import Path
import unittest

from utils.report_export_cache import (
    REPORT_EXPORT_CACHE_SESSION_KEY,
    ReportExportCacheError,
    get_report_export_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _record(
    *,
    snapshot_id: int = 1,
    sha256: str = "abc123",
) -> dict[str, object]:
    return {
        "id": snapshot_id,
        "snapshot_sha256":
            sha256,
    }


class ReportExportSessionCacheTests(
    unittest.TestCase
):
    def test_same_snapshot_builds_each_export_once(
        self,
    ):
        state: dict[str, object] = {}
        counts = {
            "excel": 0,
            "pdf": 0,
        }

        def excel_builder(
            record,
        ):
            counts["excel"] += 1
            return b"excel"

        def pdf_builder(
            record,
        ):
            counts["pdf"] += 1
            return b"pdf"

        first = get_report_export_bundle(
            _record(),
            state,
            excel_builder=
                excel_builder,
            pdf_builder=
                pdf_builder,
        )
        second = get_report_export_bundle(
            _record(),
            state,
            excel_builder=
                excel_builder,
            pdf_builder=
                pdf_builder,
        )

        self.assertIs(
            first,
            second,
        )
        self.assertEqual(
            counts,
            {
                "excel": 1,
                "pdf": 1,
            },
        )

    def test_different_snapshot_rebuilds_and_replaces_cache(
        self,
    ):
        state: dict[str, object] = {}
        counts = {
            "excel": 0,
            "pdf": 0,
        }

        def excel_builder(
            record,
        ):
            counts["excel"] += 1
            return (
                f"excel-{record['id']}"
                .encode()
            )

        def pdf_builder(
            record,
        ):
            counts["pdf"] += 1
            return (
                f"pdf-{record['id']}"
                .encode()
            )

        first = get_report_export_bundle(
            _record(
                snapshot_id=1,
                sha256="hash-1",
            ),
            state,
            excel_builder=
                excel_builder,
            pdf_builder=
                pdf_builder,
        )
        second = get_report_export_bundle(
            _record(
                snapshot_id=2,
                sha256="hash-2",
            ),
            state,
            excel_builder=
                excel_builder,
            pdf_builder=
                pdf_builder,
        )

        self.assertIsNot(
            first,
            second,
        )
        self.assertEqual(
            counts,
            {
                "excel": 2,
                "pdf": 2,
            },
        )
        self.assertIs(
            state[
                REPORT_EXPORT_CACHE_SESSION_KEY
            ],
            second,
        )

    def test_same_id_changed_hash_rebuilds(
        self,
    ):
        state: dict[str, object] = {}
        counts = {
            "excel": 0,
            "pdf": 0,
        }

        def excel_builder(
            record,
        ):
            counts["excel"] += 1
            return b"excel"

        def pdf_builder(
            record,
        ):
            counts["pdf"] += 1
            return b"pdf"

        get_report_export_bundle(
            _record(
                sha256="hash-1"
            ),
            state,
            excel_builder=
                excel_builder,
            pdf_builder=
                pdf_builder,
        )
        get_report_export_bundle(
            _record(
                sha256="hash-2"
            ),
            state,
            excel_builder=
                excel_builder,
            pdf_builder=
                pdf_builder,
        )

        self.assertEqual(
            counts,
            {
                "excel": 2,
                "pdf": 2,
            },
        )

    def test_missing_integrity_hash_is_rejected(
        self,
    ):
        with self.assertRaises(
            ReportExportCacheError
        ):
            get_report_export_bundle(
                {
                    "id": 1,
                    "snapshot_sha256":
                        "",
                },
                {},
                excel_builder=
                    lambda record: b"x",
                pdf_builder=
                    lambda record: b"y",
            )


class ReportPageExportCacheContracts(
    unittest.TestCase
):
    def test_reports_page_uses_session_export_bundle(
        self,
    ):
        source = (
            PROJECT_ROOT
            / "pages"
            / "reports.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "get_report_export_bundle(",
            source,
        )
        self.assertIn(
            "st.session_state",
            source,
        )
        self.assertNotIn(
            "build_excel_report(",
            source,
        )
        self.assertNotIn(
            "build_pdf_report(",
            source,
        )

    def test_export_cache_is_not_global_streamlit_cache(
        self,
    ):
        source = (
            PROJECT_ROOT
            / "utils"
            / "report_export_cache.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "@st.cache_data",
            source,
        )
        self.assertNotIn(
            "@st.cache_resource",
            source,
        )


if __name__ == "__main__":
    unittest.main()
