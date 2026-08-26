from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = (
    PROJECT_ROOT
    / "pages"
    / "dashboard.py"
)
EVENT_CONTROL_PATH = (
    PROJECT_ROOT
    / "pages"
    / "event_control.py"
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


class OperationalConsoleContracts(
    unittest.TestCase
):
    def test_dashboard_uses_compact_operational_header_and_event_strip(
        self,
    ):
        source = DASHBOARD_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "render_operational_page_header(",
            source,
        )
        self.assertIn(
            "render_operational_event_strip(",
            source,
        )
        self.assertNotIn(
            "render_dashboard_command_panel(",
            source,
        )
        self.assertNotIn(
            'event_columns[0].metric(\n    "Active Event"',
            source,
        )

    def test_event_control_uses_compact_operational_components(
        self,
    ):
        source = EVENT_CONTROL_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "render_operational_page_header(",
            source,
        )
        self.assertIn(
            "render_event_control_strip(",
            source,
        )
        self.assertNotIn(
            "render_event_control_summary(",
            source,
        )
        self.assertNotIn(
            "summary_columns = st.columns(4)",
            source,
        )

    def test_operational_identifiers_are_html_escaped(
        self,
    ):
        source = UI_PATH.read_text(
            encoding="utf-8-sig"
        )

        for token in (
            "escape(event_name)",
            "escape(value)",
            "escape(alert_text)",
        ):
            self.assertIn(
                token,
                source,
            )

    def test_operational_values_wrap_without_ellipsis(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            ".mdrrmo-ops-event__name",
            source,
        )
        self.assertIn(
            ".mdrrmo-ops-field__value",
            source,
        )
        self.assertIn(
            "overflow-wrap: anywhere;",
            source,
        )
        self.assertIn(
            "white-space: normal;",
            source,
        )
        self.assertNotIn(
            "text-overflow: ellipsis",
            source,
        )

    def test_operational_workspace_uses_sans_serif_type(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        for selector in (
            ".mdrrmo-ops-page-header__title",
            ".mdrrmo-ops-event__name",
            ".mdrrmo-ops-field__value",
        ):
            start = source.index(
                selector
            )
            snippet = source[
                start:start + 500
            ]

            self.assertIn(
                "font-family: var(--font-body);",
                snippet,
            )

    def test_event_strip_is_neutral_not_dark_hero(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        start = source.index(
            ".mdrrmo-ops-event {"
        )
        snippet = source[
            start:start + 600
        ]

        self.assertIn(
            "background: var(--surface-card);",
            snippet,
        )
        self.assertIn(
            "border-top: 3px solid var(--gov-gold);",
            snippet,
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


if __name__ == "__main__":
    unittest.main()
