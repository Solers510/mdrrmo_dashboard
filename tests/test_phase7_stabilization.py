from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
import subprocess
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def tracked_python_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "*.py"],
        cwd=PROJECT_ROOT,
        text=True,
    )
    return [
        Path(line.strip())
        for line in output.splitlines()
        if line.strip()
    ]


def application_files() -> list[Path]:
    allowed_roots = {
        "pages",
        "services",
        "database",
        "utils",
        "config",
        "components",
        "scripts",
    }

    result = []

    for path in tracked_python_files():
        if path == Path("app.py"):
            result.append(path)
        elif (
            path.parts
            and path.parts[0] in allowed_roots
        ):
            result.append(path)

    return result


def is_named_call(
    node: ast.Call,
    *,
    owner: str,
    attribute: str,
) -> bool:
    func = node.func

    return (
        isinstance(func, ast.Attribute)
        and func.attr == attribute
        and isinstance(func.value, ast.Name)
        and func.value.id == owner
    )


class Phase7StructuralContracts(unittest.TestCase):
    def test_no_duplicate_top_level_definitions(self):
        duplicates = []

        for relative in application_files():
            source = (
                PROJECT_ROOT / relative
            ).read_text(encoding="utf-8-sig")

            tree = ast.parse(
                source,
                filename=str(relative),
            )

            names = defaultdict(list)

            for node in tree.body:
                if isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.ClassDef,
                    ),
                ):
                    names[node.name].append(
                        node.lineno
                    )

            for name, lines in names.items():
                if len(lines) > 1:
                    duplicates.append(
                        (
                            relative.as_posix(),
                            name,
                            lines,
                        )
                    )

        self.assertEqual(
            duplicates,
            [],
            msg=(
                "Duplicate top-level definitions found: "
                f"{duplicates}"
            ),
        )

    def test_no_raw_streamlit_exception_calls(self):
        offenders = []

        for relative in application_files():
            source = (
                PROJECT_ROOT / relative
            ).read_text(encoding="utf-8-sig")

            tree = ast.parse(
                source,
                filename=str(relative),
            )

            if any(
                isinstance(node, ast.Call)
                and is_named_call(
                    node,
                    owner="st",
                    attribute="exception",
                )
                for node in ast.walk(tree)
            ):
                offenders.append(
                    relative.as_posix()
                )

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Raw st.exception() calls remain in: "
                f"{offenders}"
            ),
        )

    def test_no_streamlit_use_container_width_deprecation(self):
        offenders = []

        for relative in application_files():
            source = (
                PROJECT_ROOT / relative
            ).read_text(encoding="utf-8-sig")

            if "use_container_width=" in source:
                offenders.append(
                    relative.as_posix()
                )

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Deprecated use_container_width remains in: "
                f"{offenders}"
            ),
        )

    def test_no_debugger_calls_in_application_code(self):
        offenders = []

        for relative in application_files():
            source = (
                PROJECT_ROOT / relative
            ).read_text(encoding="utf-8-sig")

            tree = ast.parse(
                source,
                filename=str(relative),
            )

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "breakpoint"
                ):
                    offenders.append(
                        relative.as_posix()
                    )
                    break

                if is_named_call(
                    node,
                    owner="pdb",
                    attribute="set_trace",
                ):
                    offenders.append(
                        relative.as_posix()
                    )
                    break

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Debugger calls remain in: "
                f"{offenders}"
            ),
        )

    def test_sensitive_runtime_files_are_not_tracked(self):
        output = subprocess.check_output(
            ["git", "ls-files"],
            cwd=PROJECT_ROOT,
            text=True,
        )

        tracked = {
            line.strip().replace("\\", "/")
            for line in output.splitlines()
            if line.strip()
        }

        offenders = []

        for path in sorted(tracked):
            if path in {
                ".env",
                ".streamlit/secrets.toml",
            }:
                offenders.append(path)

            if (
                (
                    path.startswith("logs/")
                    or path.startswith("backups/")
                )
                and path != "backups/.gitkeep"
            ):
                offenders.append(path)

        self.assertEqual(
            offenders,
            [],
            msg=(
                "Sensitive/runtime files tracked: "
                f"{offenders}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
