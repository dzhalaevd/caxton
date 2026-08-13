from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar

from caxton.core.models import SpreadsheetDocument

from ._diff import Difference, DifferenceKind
from ._spec import (
    ColumnSpec,
    SpreadsheetSpec,
    TableSpec,
    WorksheetSpec,
    inspect_spec,
)

SpecInput = SpreadsheetDocument | SpreadsheetSpec
SpecT = TypeVar("SpecT")
KeyT = TypeVar("KeyT")


class SpreadsheetAssertionError(AssertionError):
    """Spreadsheet mismatch with machine-readable differences."""

    def __init__(self, differences: Sequence[Difference]) -> None:
        self.differences = tuple(differences)
        super().__init__(_format_differences(self.differences))


def assert_spreadsheet_equal(
    actual: SpecInput,
    expected: SpecInput,
    *,
    check_order: bool = True,
    check_metadata: bool = True,
) -> None:
    """Assert equality of two spreadsheet specifications.

    Both inspected specifications and source documents are accepted. Inspecting
    a source document is structural and never consumes its table row sources.

    Args:
        actual: Observed spreadsheet specification or source document.
        expected: Expected spreadsheet specification or source document.
        check_order: Whether declaration order is significant.
        check_metadata: Whether document metadata is significant.

    Raises:
        SpreadsheetAssertionError: If observable specifications differ.
    """
    actual_spec = _coerce_spec(actual)
    expected_spec = _coerce_spec(expected)
    differences: list[Difference] = []
    if check_metadata:
        _compare_value(
            actual_spec.metadata,
            expected_spec.metadata,
            path="metadata",
            differences=differences,
        )
    for field in ("styles", "theme"):
        _compare_value(
            getattr(actual_spec, field),
            getattr(expected_spec, field),
            path=field,
            differences=differences,
        )
    _compare_keyed(
        actual_spec.worksheets,
        expected_spec.worksheets,
        key=lambda worksheet: worksheet.name,
        item_path=lambda name: f"worksheet[{name!r}]",
        collection_path="worksheets",
        compare=lambda actual_item, expected_item, path: _compare_worksheet(
            actual_item,
            expected_item,
            path=path,
            differences=differences,
            check_order=check_order,
        ),
        differences=differences,
        check_order=check_order,
    )
    if differences:
        raise SpreadsheetAssertionError(differences)


def _coerce_spec(value: SpecInput) -> SpreadsheetSpec:
    if isinstance(value, SpreadsheetSpec):
        return value
    if isinstance(value, SpreadsheetDocument):
        return inspect_spec(value)
    message = (
        f"Expected SpreadsheetSpec or SpreadsheetDocument, got {type(value).__name__}"
    )
    raise TypeError(message)


def _compare_worksheet(
    actual: WorksheetSpec,
    expected: WorksheetSpec,
    *,
    path: str,
    differences: list[Difference],
    check_order: bool,
) -> None:
    _compare_value(
        actual.name,
        expected.name,
        path=f"{path}.name",
        differences=differences,
    )
    _compare_value(
        actual.freeze,
        expected.freeze,
        path=f"{path}.freeze",
        differences=differences,
    )
    _compare_value(
        actual.blocks,
        expected.blocks,
        path=f"{path}.blocks",
        differences=differences,
    )
    _compare_keyed(
        actual.tables,
        expected.tables,
        key=lambda table: table.name,
        item_path=lambda name: f"{path}.table[{name!r}]",
        collection_path=f"{path}.tables",
        compare=lambda actual_item, expected_item, item_path: _compare_table(
            actual_item,
            expected_item,
            path=item_path,
            differences=differences,
            check_order=check_order,
        ),
        differences=differences,
        check_order=check_order,
    )


def _compare_table(
    actual: TableSpec,
    expected: TableSpec,
    *,
    path: str,
    differences: list[Difference],
    check_order: bool,
) -> None:
    _compare_value(
        actual.name,
        expected.name,
        path=f"{path}.name",
        differences=differences,
    )
    _compare_value(
        actual.anchor,
        expected.anchor,
        path=f"{path}.anchor",
        differences=differences,
    )
    for field in (
        "style",
        "header_style",
        "footer",
        "rules",
        "autofilter",
        "freeze_header",
        "auto_width",
    ):
        _compare_value(
            getattr(actual, field),
            getattr(expected, field),
            path=f"{path}.{field}",
            differences=differences,
        )
    _compare_keyed(
        actual.columns,
        expected.columns,
        key=lambda column: column.id,
        item_path=lambda column_id: f"{path}.column[{column_id!r}]",
        collection_path=f"{path}.columns",
        compare=lambda actual_item, expected_item, item_path: _compare_column(
            actual_item,
            expected_item,
            path=item_path,
            differences=differences,
        ),
        differences=differences,
        check_order=check_order,
    )


def _compare_column(
    actual: ColumnSpec,
    expected: ColumnSpec,
    *,
    path: str,
    differences: list[Difference],
) -> None:
    _compare_value(
        actual.id,
        expected.id,
        path=f"{path}.id",
        differences=differences,
    )
    fields = (
        "title",
        "semantic_type",
        "source",
        "formula",
        "alignment",
        "width",
        "display_format",
        "style",
        "auto_width",
    )
    for field in fields:
        _compare_value(
            getattr(actual, field),
            getattr(expected, field),
            path=f"{path}.{field}",
            differences=differences,
        )


def _compare_keyed(  # noqa: WPS211
    actual: Sequence[SpecT],
    expected: Sequence[SpecT],
    *,
    key: Callable[[SpecT], KeyT],
    item_path: Callable[[KeyT], str],
    collection_path: str,
    compare: Callable[[SpecT, SpecT, str], None],
    differences: list[Difference],
    check_order: bool,
) -> None:
    actual_keys = tuple(key(item) for item in actual)
    expected_keys = tuple(key(item) for item in expected)
    if not _keys_are_unique(actual_keys) or not _keys_are_unique(expected_keys):
        _compare_positional(
            actual,
            expected,
            collection_path=collection_path,
            compare=compare,
            differences=differences,
        )
        return
    actual_by_key = dict(zip(actual_keys, actual, strict=True))
    expected_by_key = dict(zip(expected_keys, expected, strict=True))
    if (
        check_order
        and actual_keys != expected_keys
        and set(actual_keys) == set(expected_keys)
    ):
        differences.append(
            Difference(
                path=collection_path,
                kind=DifferenceKind.ORDER,
                expected=expected_keys,
                actual=actual_keys,
            ),
        )
    for expected_key in expected_keys:
        path = item_path(expected_key)
        if expected_key not in actual_by_key:
            differences.append(
                Difference(
                    path=path,
                    kind=DifferenceKind.MISSING,
                    expected=expected_by_key[expected_key],
                    actual=None,
                ),
            )
            continue
        compare(actual_by_key[expected_key], expected_by_key[expected_key], path)
    differences.extend(
        Difference(
            path=item_path(actual_key),
            kind=DifferenceKind.UNEXPECTED,
            expected=None,
            actual=actual_by_key[actual_key],
        )
        for actual_key in actual_keys
        if actual_key not in expected_by_key
    )


def _compare_positional(
    actual: Sequence[SpecT],
    expected: Sequence[SpecT],
    *,
    collection_path: str,
    compare: Callable[[SpecT, SpecT, str], None],
    differences: list[Difference],
) -> None:
    common_size = min(len(actual), len(expected))
    for index in range(common_size):
        compare(
            actual[index],
            expected[index],
            f"{collection_path}[{index}]",
        )
    differences.extend(
        Difference(
            path=f"{collection_path}[{index}]",
            kind=DifferenceKind.MISSING,
            expected=expected[index],
            actual=None,
        )
        for index in range(common_size, len(expected))
    )
    differences.extend(
        Difference(
            path=f"{collection_path}[{index}]",
            kind=DifferenceKind.UNEXPECTED,
            expected=None,
            actual=actual[index],
        )
        for index in range(common_size, len(actual))
    )


def _keys_are_unique(keys: Sequence[object]) -> bool:
    return len(keys) == len(set(keys))


def _compare_value(
    actual: object,
    expected: object,
    *,
    path: str,
    differences: list[Difference],
) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        _compare_mapping(actual, expected, path=path, differences=differences)
        return
    if actual != expected:
        differences.append(
            Difference(
                path=path,
                kind=DifferenceKind.VALUE,
                expected=expected,
                actual=actual,
            ),
        )


def _compare_mapping(
    actual: Mapping[object, object],
    expected: Mapping[object, object],
    *,
    path: str,
    differences: list[Difference],
) -> None:
    for key, expected_value in expected.items():
        item_path = f"{path}[{key!r}]"
        if key not in actual:
            differences.append(
                Difference(item_path, DifferenceKind.MISSING, expected_value, None),
            )
            continue
        _compare_value(
            actual[key],
            expected_value,
            path=item_path,
            differences=differences,
        )
    for key, actual_value in actual.items():
        if key not in expected:
            differences.append(
                Difference(
                    f"{path}[{key!r}]",
                    DifferenceKind.UNEXPECTED,
                    None,
                    actual_value,
                ),
            )


def _format_differences(differences: Sequence[Difference]) -> str:
    label = "difference" if len(differences) == 1 else "differences"
    lines = [f"Spreadsheet specifications differ ({len(differences)} {label})"]
    for difference in differences:
        lines.append(f"- {difference.path} [{difference.kind.value}]")
        if difference.kind is not DifferenceKind.UNEXPECTED:
            lines.append(f"  expected: {difference.expected!r}")
        if difference.kind is not DifferenceKind.MISSING:
            lines.append(f"  actual:   {difference.actual!r}")
    return "\n".join(lines)


__all__ = ("SpreadsheetAssertionError", "assert_spreadsheet_equal")
