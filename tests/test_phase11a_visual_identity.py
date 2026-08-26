from __future__ import annotations

from pathlib import Path
import struct
import tomllib
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_ROOT
    / ".streamlit"
    / "config.toml"
)
APP_PATH = PROJECT_ROOT / "app.py"
AUTH_PATH = (
    PROJECT_ROOT
    / "utils"
    / "auth.py"
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
OMDRRMO_SEAL = (
    PROJECT_ROOT
    / "assets"
    / "branding"
    / "OMDRRMO.png"
)
NAIC_SEAL = (
    PROJECT_ROOT
    / "assets"
    / "branding"
    / "bayannaic.png"
)


def _png_dimensions(
    path: Path,
) -> tuple[int, int]:
    data = path.read_bytes()

    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(
            f"{path.name} is not a PNG."
        )

    return struct.unpack(
        ">II",
        data[16:24],
    )


class BrandingAssetContracts(
    unittest.TestCase
):
    def test_official_filenames_exist_exactly(
        self,
    ):
        self.assertTrue(
            OMDRRMO_SEAL.exists()
        )
        self.assertTrue(
            NAIC_SEAL.exists()
        )

        names = {
            path.name
            for path in (
                PROJECT_ROOT
                / "assets"
                / "branding"
            ).iterdir()
            if path.is_file()
        }

        self.assertIn(
            "OMDRRMO.png",
            names,
        )
        self.assertIn(
            "bayannaic.png",
            names,
        )

    def test_branding_assets_are_high_resolution_pngs(
        self,
    ):
        for path in (
            OMDRRMO_SEAL,
            NAIC_SEAL,
        ):
            width, height = (
                _png_dimensions(
                    path
                )
            )

            self.assertGreaterEqual(
                width,
                1000,
            )
            self.assertGreaterEqual(
                height,
                1000,
            )


class PaletteContracts(
    unittest.TestCase
):
    def test_streamlit_theme_uses_approved_palette(
        self,
    ):
        data = tomllib.loads(
            CONFIG_PATH.read_text(
                encoding="utf-8-sig"
            )
        )

        theme = data["theme"]
        sidebar = theme["sidebar"]

        self.assertEqual(
            theme["primaryColor"],
            "#1549A8",
        )
        self.assertEqual(
            theme["backgroundColor"],
            "#EEF2F8",
        )
        self.assertEqual(
            sidebar["backgroundColor"],
            "#0D2461",
        )
        self.assertEqual(
            sidebar["primaryColor"],
            "#C9A227",
        )

    def test_old_generic_purple_orange_palette_is_not_used(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        ).upper()

        self.assertNotIn(
            "#934FFF",
            source,
        )
        self.assertNotIn(
            "#FF8C00",
            source,
        )


class SharedUIContracts(
    unittest.TestCase
):
    def test_app_loads_design_system_and_sidebar_brand(
        self,
    ):
        source = APP_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "load_design_system()",
            source,
        )
        self.assertIn(
            "render_sidebar_brand()",
            source,
        )

    def test_auth_uses_shared_login_and_identity_components(
        self,
    ):
        source = AUTH_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "render_login_header()",
            source,
        )
        self.assertIn(
            "render_identity_card(",
            source,
        )

    def test_ui_references_exact_official_asset_names(
        self,
    ):
        source = UI_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            '"OMDRRMO.png"',
            source,
        )
        self.assertIn(
            '"bayannaic.png"',
            source,
        )
        self.assertNotIn(
            "omdrrmo_seal.png",
            source,
        )
        self.assertNotIn(
            "naic_seal.png",
            source,
        )

    def test_css_does_not_depend_on_private_streamlit_dom(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "[data-testid=",
            source,
        )
        self.assertNotIn(
            "<script",
            source.lower(),
        )


if __name__ == "__main__":
    unittest.main()
