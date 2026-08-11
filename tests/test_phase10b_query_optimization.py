from __future__ import annotations

import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SERVICE = (
    PROJECT_ROOT
    / "services"
    / "validation_service.py"
)


class Phase10BQueryOptimizationContracts(
    unittest.TestCase
):
    def test_reconciliation_no_longer_uses_per_barangay_fetch(
        self,
    ):
        source = VALIDATION_SERVICE.read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "fetch_latest_barangay_update_for_barangay",
            source,
        )

    def test_reconciliation_uses_bulk_latest_barangay_fetch(
        self,
    ):
        source = VALIDATION_SERVICE.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "fetch_latest_barangay_updates_for_event",
            source,
        )
        self.assertIn(
            "latest_barangay_by_id",
            source,
        )

    def test_bulk_fetch_is_outside_barangay_loop(
        self,
    ):
        source = VALIDATION_SERVICE.read_text(
            encoding="utf-8-sig"
        )
        tree = ast.parse(
            source
        )

        target = next(
            node
            for node in tree.body
            if isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "get_population_reconciliation_queue"
        )

        bulk_calls = []
        loop_bulk_calls = []

        for node in ast.walk(
            target
        ):
            if isinstance(
                node,
                ast.Call,
            ):
                function = node.func
                if (
                    isinstance(
                        function,
                        ast.Name,
                    )
                    and function.id
                    == "fetch_latest_barangay_updates_for_event"
                ):
                    bulk_calls.append(
                        node
                    )

        for node in ast.walk(
            target
        ):
            if not isinstance(
                node,
                (ast.For, ast.AsyncFor),
            ):
                continue

            for inner in ast.walk(
                node
            ):
                if not isinstance(
                    inner,
                    ast.Call,
                ):
                    continue

                function = inner.func
                if (
                    isinstance(
                        function,
                        ast.Name,
                    )
                    and function.id
                    == "fetch_latest_barangay_updates_for_event"
                ):
                    loop_bulk_calls.append(
                        inner
                    )

        self.assertEqual(
            len(
                bulk_calls
            ),
            1,
        )
        self.assertEqual(
            loop_bulk_calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
