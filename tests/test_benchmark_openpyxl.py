from __future__ import annotations

from collections.abc import Callable
from io import BytesIO

import pytest
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from pytest_benchmark.fixture import BenchmarkFixture

from caxton import decimal, field, matrix, render, sheet, spreadsheet, table, text
from caxton.core.models import SpreadsheetDocument
from caxton.testing import ArtifactWorksheet, inspect_artifact

Row = dict[str, str | int]
Rows = tuple[Row, ...]
ReportOperation = Callable[[Rows], bytes]

_GROUP_COUNT = 500
_GROUP_ROW_COUNT = 10_000
_MATRIX_ROWS = 40
_MATRIX_COLUMNS = 20
_MATRIX_REPEATS = 10


def _openpyxl_grouped_report(rows: Rows) -> bytes:
    grouped: dict[str, int] = {}
    for row in rows:
        key = str(row["group"])
        grouped[key] = grouped.get(key, 0) + int(row["value"])

    workbook = Workbook()
    worksheet = workbook.active
    assert isinstance(worksheet, Worksheet)
    worksheet.title = "Grouped"
    worksheet.append(("group", "total"))
    for key, total in grouped.items():
        worksheet.append((key, total))
    return _save_workbook(workbook)


def _caxton_grouped_report(rows: Rows) -> bytes:
    document = spreadsheet(
        sheet(
            "Grouped",
            table(
                source=rows,
                columns=(
                    text(id="group", source="group").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )
    return _render_with_caxton(document)


def _openpyxl_matrix_report(rows: Rows) -> bytes:
    row_keys: dict[str, None] = {}
    column_keys: dict[str, None] = {}
    cells: dict[tuple[str, str], int] = {}
    for item in rows:
        row_key = str(item["row"])
        column_key = str(item["column"])
        row_keys.setdefault(row_key, None)
        column_keys.setdefault(column_key, None)
        cell_key = row_key, column_key
        cells[cell_key] = cells.get(cell_key, 0) + int(item["value"])

    workbook = Workbook()
    worksheet = workbook.active
    assert isinstance(worksheet, Worksheet)
    worksheet.title = "Matrix"
    worksheet.append(("row", *column_keys))
    for row_key in row_keys:
        worksheet.append(
            (
                row_key,
                *(cells.get((row_key, column_key)) for column_key in column_keys),
            ),
        )
    return _save_workbook(workbook)


def _caxton_matrix_report(rows: Rows) -> bytes:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=rows,
                row=field("row"),
                column=field("column"),
                value=field("value").agg(sum),
            ),
        ),
    )
    return _render_with_caxton(document)


def _save_workbook(workbook: Workbook) -> bytes:
    target = BytesIO()
    workbook.save(target)
    workbook.close()
    return target.getvalue()


def _render_with_caxton(document: SpreadsheetDocument) -> bytes:
    result = render(document, backend="openpyxl")
    if result.data is None:
        message = "In-memory render did not return artifact bytes"
        raise RuntimeError(message)
    return result.data


def _cell_values(worksheet: ArtifactWorksheet) -> tuple[tuple[str, object], ...]:
    return tuple((cell.address, cell.value) for cell in worksheet.cells)


@pytest.fixture(scope="module")
def grouped_rows() -> Rows:
    return tuple(
        {
            "group": f"group-{index % _GROUP_COUNT}",
            "value": index % 17,
        }
        for index in range(_GROUP_ROW_COUNT)
    )


@pytest.fixture(scope="module")
def matrix_rows() -> Rows:
    rows: list[Row] = []
    for repeat in range(_MATRIX_REPEATS):
        rows.extend(
            {
                "row": f"row-{row}",
                "column": f"column-{column}",
                "value": repeat + 1,
            }
            for row in range(_MATRIX_ROWS)
            for column in range(_MATRIX_COLUMNS)
        )
    return tuple(rows)


@pytest.mark.benchmark(group="grouped-report-openpyxl-end-to-end")
@pytest.mark.parametrize(
    "operation",
    [_openpyxl_grouped_report, _caxton_grouped_report],
    ids=("pure-python-openpyxl", "caxton-openpyxl"),
)
def test_grouped_report_end_to_end(
    benchmark: BenchmarkFixture,
    grouped_rows: Rows,
    operation: ReportOperation,
) -> None:
    payload = benchmark(operation, grouped_rows)

    assert payload.startswith(b"PK")


@pytest.mark.benchmark(group="matrix-report-openpyxl-end-to-end")
@pytest.mark.parametrize(
    "operation",
    [_openpyxl_matrix_report, _caxton_matrix_report],
    ids=("pure-python-openpyxl", "caxton-openpyxl"),
)
def test_matrix_report_end_to_end(
    benchmark: BenchmarkFixture,
    matrix_rows: Rows,
    operation: ReportOperation,
) -> None:
    payload = benchmark(operation, matrix_rows)

    assert payload.startswith(b"PK")


def test_grouped_workloads_are_equivalent(grouped_rows: Rows) -> None:
    direct = inspect_artifact(_openpyxl_grouped_report(grouped_rows))
    caxton = inspect_artifact(_caxton_grouped_report(grouped_rows))

    assert _cell_values(direct.worksheet("Grouped")) == _cell_values(
        caxton.worksheet("Grouped"),
    )


def test_matrix_workloads_are_equivalent(matrix_rows: Rows) -> None:
    direct = inspect_artifact(_openpyxl_matrix_report(matrix_rows))
    caxton = inspect_artifact(_caxton_matrix_report(matrix_rows))

    assert _cell_values(direct.worksheet("Matrix")) == _cell_values(
        caxton.worksheet("Matrix"),
    )
