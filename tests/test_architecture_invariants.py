from __future__ import annotations

import ast
import dataclasses
from collections.abc import Iterable, Iterator, Mapping
from importlib.util import resolve_name
from io import BytesIO
from pathlib import Path

import pytest

from caxton import (
    RowSourceInput,
    SpreadsheetDocument,
    core as core_package,
    decimal,
    field,
    matrix,
    ref,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    validate,
    write as write_document,
)
from caxton.core.ir import SPREADSHEET_IR_VERSION
from caxton.core.models import DocumentKind
from caxton.core.rendering import RendererCapabilities, RequiredCapabilities
from caxton.testing import (
    Rows,
    assert_spreadsheet_equal,
    inspect_artifact,
    inspect_layout,
    inspect_spec,
)

_BACKEND_MODULES = frozenset(("openpyxl", "xlsxwriter"))
_FORBIDDEN_CORE_DEPENDENCIES = (
    "caxton.api",
    "caxton._source",
    "caxton._spreadsheet",
    "caxton._xlsx",
    "caxton._io",
    "caxton._pipeline",
    "caxton.testing",
    *_BACKEND_MODULES,
)


def _sales_document(source: RowSourceInput) -> SpreadsheetDocument:
    return spreadsheet(
        sheet(
            "Sales",
            table(
                source=source,
                columns=(
                    decimal(id="gross", source="gross"),
                    decimal(id="cost", source="cost"),
                    decimal(id="margin", source=ref("gross") - ref("cost")),
                ),
                name="sales",
            ),
        ),
    )


def test_compilation_preserves_semantic_model() -> None:
    document = _sales_document([{"gross": 100, "cost": 40}])
    before_compilation = inspect_spec(document)

    inspect_layout(document, rows=Rows.all())

    assert_spreadsheet_equal(document, before_compilation)


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_placements_match_rendered_artifact(backend: str) -> None:
    document = spreadsheet(
        sheet(
            "Ordinary",
            table(
                source=[{"label": "A", "value": 1}, {"label": "B", "value": 2}],
                columns=(
                    text(id="label", source="label"),
                    decimal(id="value", source="value"),
                ),
                anchor="C3",
            ),
        ),
        sheet(
            "Grouped",
            table(
                source=[
                    {"region": "North", "store": "A", "value": 1},
                    {"region": "North", "store": "B", "value": 2},
                    {"region": "South", "store": "C", "value": 3},
                ],
                columns=(
                    text(id="region", source="region").grouped(merge=True),
                    text(id="store", source="store").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
                anchor="E5",
            ),
        ),
        sheet(
            "Matrix",
            matrix(
                source=[
                    {"region": "North", "store": "A", "month": "Jan", "value": 1},
                    {"region": "North", "store": "B", "month": "Jan", "value": 2},
                    {"region": "South", "store": "C", "month": "Feb", "value": 3},
                ],
                row=(
                    text(id="region", source="region").grouped(merge=True),
                    field("store"),
                ),
                column=field("month"),
                value=field("value").agg(sum),
                anchor="B4",
            ),
        ),
    )

    layout = inspect_layout(document, rows=Rows.all(), backend=backend)
    artifact = inspect_artifact(render(document, backend=backend))

    for worksheet_name in ("Ordinary", "Grouped", "Matrix"):
        worksheet_layout = layout.worksheet(worksheet_name)
        worksheet_artifact = artifact.worksheet(worksheet_name)
        placement = worksheet_layout.blocks[0]

        assert worksheet_artifact.used_range == placement.cell_range
        assert worksheet_artifact.used_range is not None
        assert worksheet_artifact.used_range.partition(":")[0] == placement.anchor
        assert worksheet_artifact.merged_ranges == (
            worksheet_layout.tables[0].merged_ranges
        )


def test_validation_preserves_model_without_rows() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"gross": 100, "cost": 40}

    document = _sales_document(rows())
    before_validation = inspect_spec(document)

    validate(document)

    assert_spreadsheet_equal(document, before_validation)
    assert not visited


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_public_results_exclude_backend_objects(backend: str) -> None:
    document = _sales_document([{"gross": 100, "cost": 40}])
    rendered = render(document, backend=backend)
    target = BytesIO()

    returned_values = (
        document,
        rendered,
        write_document(document, target, backend=backend),
        inspect_spec(document),
        inspect_layout(document, rows=Rows.all()),
        inspect_artifact(rendered.data or b""),
    )

    assert _backend_native_types(returned_values) == set()


def _backend_native_types(values: Iterable[object]) -> set[str]:
    found: set[str] = set()
    pending = list(values)
    visited: set[int] = set()
    while pending:
        value = pending.pop()
        if id(value) in visited:
            continue
        visited.add(id(value))
        value_type = type(value)
        if value_type.__module__.partition(".")[0] in _BACKEND_MODULES:
            found.add(f"{value_type.__module__}.{value_type.__qualname__}")
        pending.extend(_public_value_children(value))
    return found


def _public_value_children(value: object) -> Iterable[object]:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(getattr(value, field.name) for field in dataclasses.fields(value))
    if isinstance(value, Mapping):
        return (*value.keys(), *value.values())
    if isinstance(value, (tuple, list, set, frozenset)):
        return value
    return ()


def test_core_excludes_outer_and_backend_imports() -> None:
    core_file = core_package.__file__
    assert core_file is not None
    core_root = Path(core_file).parent

    violations = {
        violation
        for source_path in core_root.rglob("*.py")
        for violation in _forbidden_imports(source_path, core_root)
    }

    assert violations == set()


def test_no_catch_all_internal_package() -> None:
    core_file = core_package.__file__
    assert core_file is not None
    implementation = Path(core_file).parent.parent / "_internal"

    assert not implementation.exists()


def _forbidden_imports(source_path: Path, core_root: Path) -> Iterator[str]:
    syntax = ast.parse(source_path.read_text(encoding="utf-8"), filename=source_path)
    package = _package_name(source_path, core_root)
    for node in ast.walk(syntax):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported in _imported_modules(node, package):
            if _is_forbidden_core_dependency(imported):
                relative_path = source_path.relative_to(core_root.parent)
                yield f"{relative_path}:{node.lineno} imports {imported}"


def _package_name(source_path: Path, core_root: Path) -> str:
    relative_parent = source_path.relative_to(core_root).parent
    return ".".join(("caxton", "core", *relative_parent.parts))


def _imported_modules(
    node: ast.Import | ast.ImportFrom,
    package: str,
) -> Iterator[str]:
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
        return
    module = node.module or ""
    imported = (
        resolve_name(f"{'.' * node.level}{module}", package) if node.level else module
    )
    yield imported
    yield from (f"{imported}.{alias.name}" for alias in node.names if alias.name != "*")


def _is_forbidden_core_dependency(module: str) -> bool:
    return any(
        module == forbidden or module.startswith(f"{forbidden}.")
        for forbidden in _FORBIDDEN_CORE_DEPENDENCIES
    )


@pytest.mark.parametrize(
    "other_family",
    tuple(kind for kind in DocumentKind if kind is not DocumentKind.SPREADSHEET),
)
def test_capabilities_are_isolated_by_family(
    other_family: DocumentKind,
) -> None:
    capabilities = RendererCapabilities(
        ir_versions={
            DocumentKind.SPREADSHEET: frozenset((SPREADSHEET_IR_VERSION,)),
        },
        features=frozenset(("table",)),
    )
    required = RequiredCapabilities(
        document_kind=other_family,
        ir_versions=frozenset((SPREADSHEET_IR_VERSION,)),
        features=frozenset(("table",)),
    )

    assert not capabilities.supports(required)
