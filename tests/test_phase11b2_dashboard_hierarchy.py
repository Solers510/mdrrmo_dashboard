from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = (
    PROJECT_ROOT
    / "pages"
    / "dashboard.py"
)
UI_PATH = (
    PROJECT_ROOT
    / "utils"
    / "ui.py"
)
CSS_PATH = (
    PROJECT_ROOT
    / "styles"
    / "mdrrmo.css"
)


class DashboardHierarchyContracts(
    unittest.TestCase
):
    def test_dashboard_surfaces_attention_before_summary(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        attention = source.index(
            'title="Attention Required"'
        )
        summary = source.index(
            'title="Current Evacuation Summary"'
        )

        self.assertLess(
            attention,
            summary,
        )

    def test_dashboard_uses_custom_attention_and_kpi_components(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "render_attention_required(",
            source,
        )
        self.assertIn(
            "render_kpi_grid(",
            source,
        )
        self.assertIn(
            "render_dashboard_mode_status(",
            source,
        )

    def test_old_redundant_metric_sections_are_removed_from_top_level(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            'st.subheader(\n    "Affected Population"',
            source,
        )
        self.assertNotIn(
            'st.subheader(\n    "Immediate Operational Concerns"',
            source,
        )
        self.assertNotIn(
            "affected_columns = st.columns(3)",
            source,
        )
        self.assertNotIn(
            "concern_columns = st.columns(4)",
            source,
        )

    def test_attention_includes_validation_and_reconciliation_exceptions(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        for token in (
            '"Pending Validation"',
            '"Needs Correction"',
            '"Record Needs Data Checking"',
            '"Population Consistency Issue"',
        ):
            self.assertIn(
                token,
                source,
            )

        self.assertIn(
            "_counted_label(",
            source,
        )

    def test_freshness_is_visible_before_detail_tabs(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        freshness = source.index(
            'title="Reporting & Freshness"'
        )
        tabs = source.index(
            "barangay_tab, evacuation_tab, quality_tab"
        )

        self.assertLess(
            freshness,
            tabs,
        )

    def test_dashboard_ui_escapes_dynamic_card_text(
        self,
    ):
        import re

        source = UI_PATH.read_text(
            encoding="utf-8-sig"
        )

        patterns = (
            r'escape\(\s*str\(item\["value"\]\)\s*\)',
            r'escape\(\s*str\(item\["label"\]\)\s*\)',
            r'escape\(\s*str\(meta\)\s*\)',
        )

        for pattern in patterns:
            self.assertRegex(
                source,
                re.compile(
                    pattern,
                    flags=re.MULTILINE,
                ),
            )

    def test_dashboard_cards_use_single_primary_accent_and_semantic_attention(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "border-top: 3px solid var(--gov-blue);",
            source,
        )
        self.assertIn(
            "border-left-color: var(--warning);",
            source,
        )
        self.assertIn(
            "border-left-color: var(--danger);",
            source,
        )

    def test_no_private_streamlit_dom_selector_added(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "[data-testid=",
            source,
        )


class DashboardPolishContracts(
    unittest.TestCase
):
    def test_compact_kpis_use_balanced_three_column_desktop_grid(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        start = source.index(
            ".mdrrmo-kpi-grid--compact {"
        )
        snippet = source[
            start:start + 260
        ]

        self.assertIn(
            "repeat(",
            snippet,
        )
        self.assertIn(
            "3,",
            snippet,
        )
        self.assertIn(
            "minmax(0, 1fr)",
            snippet,
        )

    def test_compact_grid_has_two_and_one_column_breakpoints(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "@media (max-width: 1050px)",
            source,
        )
        self.assertIn(
            "@media (max-width: 700px)",
            source,
        )

    def test_displacement_location_uses_clear_operational_categories(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            'title="Current Evacuation Summary"',
            source,
        )
        self.assertIn(
            "render_current_evacuation_picture(",
            source,
        )
        self.assertNotIn(
            '"Not Displaced — Families"',
            source,
        )
        self.assertNotIn(
            '"Not Displaced — Individuals"',
            source,
        )
        self.assertNotIn(
            "Affected — Not Recorded as Displaced",
            source,
        )

    def test_relative_age_grammar_has_no_day_parentheses(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "day(s) ago",
            source,
        )
        self.assertIn(
            '"1 day ago"',
            source,
        )
        self.assertIn(
            'f"{days} days ago"',
            source,
        )

    def test_attention_labels_are_count_aware(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "def _counted_label(",
            source,
        )
        self.assertIn(
            '"Impassable Road"',
            source,
        )
        self.assertIn(
            '"Medical Case"',
            source,
        )
        self.assertIn(
            '"Record Needs Data Checking"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
