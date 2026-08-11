from __future__ import annotations

from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "pages" / "dashboard.py"

class Phase11B3NullSafetyContracts(unittest.TestCase):
    def test_reconciliation_missing_values_are_not_int_coerced(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("def format_optional_count(", source)
        self.assertIn("if value is None:", source)
        self.assertIn('return "—"', source)
        self.assertNotIn("int(row['barangay_inside_families'])", source)
        self.assertNotIn("int(row['barangay_inside_individuals'])", source)

    def test_barangay_routine_table_uses_compact_power_water_column(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")
        self.assertIn('"Power / Water"', source)
        self.assertNotIn('"Utilities": (', source)

    def test_four_item_detail_summaries_are_not_compact_three_column_grids(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")
        evac_start = source.index('title="Evacuation Center Operations"')
        quality_start = source.index('title="Source Reconciliation"')
        evac = source[evac_start:quality_start]
        quality = source[quality_start:]
        evac_grid = evac[evac.index("render_kpi_grid("):evac.index("if not evacuation_rows:")]
        quality_grid = quality[quality.index("render_kpi_grid("):quality.index("if not dashboard[")]
        self.assertNotIn("compact=True", evac_grid)
        self.assertNotIn("compact=True", quality_grid)

if __name__ == "__main__":
    unittest.main()
