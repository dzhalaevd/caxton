import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

_SCRIPT = runpy.run_path(
    str(Path(__file__).parents[1] / "scripts/check_api_compatibility.py")
)
_NORMALIZE = cast("Callable[[str], frozenset[str]]", _SCRIPT["normalized_breakages"])
_ALLOWED = cast("Callable[[str], frozenset[str] | None]", _SCRIPT["allowed_breakages"])


def test_breakages_ignore_source_line_numbers() -> None:
    output = (
        "src/caxton/api/columns.py:12: text(column_id): Parameter was removed\n"
        "src/caxton/api/spreadsheet.py:99: table(rows): Parameter was removed\n"
    )

    assert _NORMALIZE(output) == {
        "src/caxton/api/columns.py: text(column_id): Parameter was removed",
        "src/caxton/api/spreadsheet.py: table(rows): Parameter was removed",
    }


def test_api_allowlist_is_scoped_to_one_baseline() -> None:
    assert _ALLOWED("v0.1.4")
    assert _ALLOWED("v0.1.5") is None
