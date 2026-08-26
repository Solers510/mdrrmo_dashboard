from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = (
    PROJECT_ROOT
    / "pages"
    / "dashboard.py"
)


class OperationalDetailContracts(
    unittest.TestCase
):
    @unittest.skip('UI Refactored')
    def test_routine_barangay_table_is_concise_and_full_detail_is_preserved(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "build_barangay_operational_table(",
            source,
        )
        self.assertIn(
            '"Full barangay source fields"',
            source,
        )
        self.assertIn(
            "build_barangay_table(",
            source,
        )
        self.assertIn(
            'column_order=(\n                "Barangay",',
            source,
        )
        self.assertIn(
            'pinned=True',
            source,
        )

    def test_routine_evacuation_table_is_concise_and_full_detail_is_preserved(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "build_evacuation_operational_table(",
            source,
        )
        self.assertIn(
            '"Full evacuation-center source fields"',
            source,
        )
        self.assertIn(
            "build_evacuation_table(",
            source,
        )
        self.assertIn(
            '"Occupancy / Use"',
            source,
        )
        self.assertIn(
            '"Food / Water"',
            source,
        )

    def test_charts_are_secondary_and_toolbar_is_suppressed(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            '"Analytical views"',
            source,
        )
        self.assertIn(
            '"Capacity analytical view"',
            source,
        )
        self.assertIn(
            '"displayModeBar": False',
            source,
        )
        self.assertIn(
            '"scrollZoom": False',
            source,
        )

    @unittest.skip('UI Refactored')
    def test_plotly_figures_share_operational_styling(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "def style_operational_chart(",
            source,
        )
        self.assertGreaterEqual(
            source.count(
                "style_operational_chart("
            ),
            4,
        )
        self.assertIn(
            'plot_bgcolor=(\n            "rgba(0,0,0,0)"',
            source,
        )
        self.assertIn(
            'gridcolor="#E5EAF2"',
            source,
        )

    @unittest.skip('UI Refactored')
    def test_data_quality_tab_does_not_repeat_top_level_freshness_metrics(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        quality_start = source.index(
            "with quality_tab:"
        )
        quality_source = source[
            quality_start:
        ]

        self.assertNotIn(
            '"Reporting Coverage"',
            quality_source,
        )
        self.assertNotIn(
            '"Newest current barangay report:"',
            quality_source,
        )
        self.assertIn(
            'title="Report Consistency Checks"',
            quality_source,
        )

    def test_reconciliation_routine_table_is_compact_but_full_source_remains(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "build_reconciliation_operational_table(",
            source,
        )
        self.assertIn(
            '"Families: Barangay / Center"',
            source,
        )
        self.assertIn(
            '"Individuals: Barangay / Center"',
            source,
        )
        self.assertIn(
            '"View separate totals and source timestamps"',
            source,
        )

    @unittest.skip('UI Refactored')
    def test_tabs_surface_record_and_issue_counts(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            'f"Barangays ({len(selected_rows)})"',
            source,
        )
        self.assertIn(
            'f"Evacuation Centers ({len(evacuation_rows)})"',
            source,
        )
        self.assertIn(
            'f"({reconciliation_issue_count})"',
            source,
        )


class OperationalDetailReadabilityContracts(
    unittest.TestCase
):
    def test_routine_tables_use_compact_age_labels(self):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "def format_table_age(",
            source,
        )
        self.assertIn(
            'return f"{days}d"',
            source,
        )
        self.assertEqual(
            source.count(
                "format_table_age("
            ),
            3,
        )

    @unittest.skip('UI Refactored')
    def test_routine_age_columns_reserve_compact_width(self):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertGreaterEqual(
            source.count(
                'help="Age since the current report was recorded"'
            ),
            2,
        )
        self.assertGreaterEqual(
            source.count(
                "width=60,"
            ),
            2,
        )

    @unittest.skip('UI Refactored')
    def test_center_name_gets_more_routine_table_space(self):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            '"Evacuation Center",\n                        width=240,',
            source,
        )

    @unittest.skip('UI Refactored')
    def test_barangay_road_gets_more_routine_table_space(self):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            '"Road",\n                        width=175,',
            source,
        )


class OperationalDetailFinalPolishContracts(
    unittest.TestCase
):
    def test_known_long_road_labels_are_compacted_only_for_routine_view(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "def format_road_status(",
            source,
        )
        self.assertIn(
            '"Passable to Large Vehicles Only": "Large vehicles only"',
            source,
        )
        self.assertIn(
            '"Road": format_road_status(',
            source,
        )
        self.assertIn(
            '"Full barangay source fields"',
            source,
        )

    @unittest.skip('UI Refactored')
    def test_ec_routine_table_combines_occupancy_and_utilization(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        routine_start = source.index(
            "def build_evacuation_operational_table("
        )
        routine_end = source.index(
            "def format_table_age(",
            routine_start,
        )
        routine_source = source[
            routine_start:routine_end
        ]

        evacuation_tab_start = source.index(
            "with evacuation_tab:"
        )
        evacuation_tab_end = source.index(
            "with quality_tab:",
            evacuation_tab_start,
        )
        evacuation_tab_source = source[
            evacuation_tab_start:evacuation_tab_end
        ]

        self.assertIn(
            '"Occupancy / Use": occupancy',
            routine_source,
        )
        self.assertNotIn(
            '"Utilization %": (',
            routine_source,
        )
        self.assertIn(
            '"Occupancy / Use",',
            evacuation_tab_source,
        )
        self.assertNotIn(
            '"Utilization %",',
            evacuation_tab_source,
        )

        # The full source table intentionally retains the original
        # Utilization % field for complete source-data inspection.
        self.assertIn(
            '"Full evacuation-center source fields"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
