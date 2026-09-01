"""Failing regressions for known grouping, aggregation, and matrix defects.

Every test here encodes an invariant the library does not hold yet, so the
module is expected to be red until the matching defect is fixed. Each test
states the invariant it protects rather than the behaviour observed today.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from caxton import (
    CaxtonError,
    Column,
    Expression,
    InvalidOperationError,
    Matrix,
    ValidationError,
    decimal,
    field,
    link,
    matrix,
    ref,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    title,
    validate,
)
from caxton._internal.compiler import SpreadsheetCompiler  # noqa: PLC2701
from caxton._internal.requirements import (  # noqa: PLC2701
    analyze_spreadsheet_requirements,
)
from caxton.testing import Rows, inspect_artifact, inspect_layout

_COLUMN_LIMIT = 16_384
_OVERSIZED = _COLUMN_LIMIT + 16


def _wide_rows(column_count: int) -> Iterator[dict[str, object]]:
    """Yield one record per distinct column key on a single matrix row.

    Yields:
        One record per generated column key.
    """
    for index in range(column_count):
        yield {"row": "only", "column": index, "value": 1}


def _summed_value() -> Column:
    return decimal(id="value", source=field("value").agg(sum))


def _pivot(
    rows: object,
    *,
    row: Column | Expression | None = None,
    value: Column | None = None,
) -> Matrix:
    return matrix(
        source=rows,
        row=field("row") if row is None else row,
        column=field("column"),
        value=_summed_value() if value is None else value,
    )


def test_matrix_beyond_column_limit_is_rejected() -> None:
    """A matrix wider than the sheet must fail with a Caxton diagnostic."""
    document = spreadsheet(sheet("Matrix", _pivot(_wide_rows(_OVERSIZED))))

    with pytest.raises(ValidationError) as captured:
        render(document, backend="xlsxwriter")

    issue = captured.value.issues[0]
    assert issue.code == "sheet_bounds_exceeded"
    assert issue.context["dimensions"] == ("columns",)
    assert issue.context["max_columns"] == _COLUMN_LIMIT


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_matrix_columns_are_never_dropped(backend: str) -> None:
    """Rendering must refuse an oversized matrix or keep every declared cell."""
    document = spreadsheet(sheet("Matrix", _pivot(_wide_rows(_OVERSIZED))))

    try:
        result = render(document, backend=backend)
    except CaxtonError:
        return

    worksheet = inspect_artifact(result).worksheet("Matrix")

    assert len(worksheet.cells) == 2 * (_OVERSIZED + 1)


def test_aggregate_cannot_read_an_aggregate() -> None:
    """An aggregate reading an aggregate column is a structural error."""
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"shop": "A", "value": 1}],
                columns=(
                    text(id="shop", source="shop").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                    decimal(id="doubled", source=ref("total").agg(sum)),
                ),
            ),
        ),
    )

    with pytest.raises(ValidationError):
        validate(document)


def test_compile_validated_guards_aggregate_scope() -> None:
    """The aggregation layer must defend its validation precondition."""
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"shop": "A", "value": 1}],
                columns=(
                    text(id="shop", source="shop"),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )

    with pytest.raises(InvalidOperationError) as captured:
        SpreadsheetCompiler().compile_validated(document)

    assert captured.value.path == 'worksheet["Summary"].block[0].column["shop"]'


def test_filtered_input_is_not_evaluated() -> None:
    """Single-pass caching must preserve filter-before-input semantics."""
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"active": False}],
                columns=(
                    decimal(
                        id="total",
                        source=field("missing").agg(
                            sum,
                            where=field("active"),
                            default=0,
                        ),
                    ),
                ),
            ),
        ),
    )

    summary = inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]

    assert summary.row(0).values["total"] == 0


def test_matrix_rejects_nested_aggregate() -> None:
    """Matrices must reject nested aggregates exactly as tables do."""
    document = spreadsheet(
        sheet(
            "Matrix",
            _pivot(
                [{"row": "A", "column": "X", "value": 1}],
                value=decimal(id="value", source=field("value").agg(sum) * 2),
            ),
        ),
    )

    with pytest.raises(ValidationError):
        validate(document)


def test_matrix_dimension_grouping_is_kept() -> None:
    """Declared dimension ordering must be honoured or rejected, never dropped."""
    rows = [
        {"row": "B", "column": "X", "value": 1},
        {"row": "A", "column": "X", "value": 2},
    ]
    document = spreadsheet(
        sheet(
            "Matrix",
            _pivot(rows, row=text(id="row", source="row").grouped(order="ascending")),
        ),
    )

    try:
        validate(document)
    except ValidationError:
        return

    pivot = inspect_layout(document, rows=Rows.all()).worksheet("Matrix").tables[0]

    assert [row.values["row"] for row in pivot.rows] == ["A", "B"]


def test_matrix_row_dimension_merge_is_kept() -> None:
    """Row-dimension merge intent must reach the compiled matrix layout."""
    rows = [
        {"region": "North", "row": "A", "column": "X", "value": 1},
        {"region": "North", "row": "B", "column": "X", "value": 2},
    ]
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=rows,
                row=(
                    text(id="region", source="region").grouped(merge=True),
                    field("row"),
                ),
                column=field("column"),
                value=_summed_value(),
            ),
        ),
    )

    pivot = inspect_layout(document, rows=Rows.all()).worksheet("Matrix").tables[0]

    assert pivot.merged_ranges == ("A2:A3",)


def test_matrix_column_merge_is_rejected() -> None:
    """A merge on flattened matrix headers must report unsupported intent."""
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=[{"row": "A", "column": "X", "value": 1}],
                row=field("row"),
                column=text(id="column", source="column").grouped(merge=True),
                value=_summed_value(),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert {issue.code for issue in captured.value.issues} == {
        "matrix_column_dimension_merge",
    }


def test_matrix_headers_survive_hostile_keys() -> None:
    """Generated disambiguators must not collide with a literal key title."""
    rows = [
        {"row": "A", "column": 1, "value": 1},
        {"row": "A", "column": "1", "value": 1},
        {"row": "A", "column": "1 [int] #1", "value": 1},
    ]
    document = spreadsheet(sheet("Matrix", _pivot(rows)))

    pivot = inspect_layout(document, rows=Rows.none()).worksheet("Matrix").tables[0]
    titles = [column.title for column in pivot.columns[1:]]

    assert len(titles) == len(set(titles))


def test_matrix_blank_keys_stay_visible() -> None:
    """Empty and whitespace keys must render an identifiable header."""
    rows = [
        {"row": "A", "column": "", "value": 1},
        {"row": "A", "column": "   ", "value": 2},
    ]
    document = spreadsheet(sheet("Matrix", _pivot(rows)))

    pivot = inspect_layout(document, rows=Rows.none()).worksheet("Matrix").tables[0]

    assert all(column.title.strip() for column in pivot.columns)


def test_matrix_lookup_matches_group_identity() -> None:
    """Column lookup must use the same key identity that grouping uses."""
    nan = float("nan")
    rows = [
        {"row": "A", "column": nan, "value": 1},
        {"row": "A", "column": float("nan"), "value": 2},
    ]
    document = spreadsheet(sheet("Matrix", _pivot(rows)))

    pivot = inspect_layout(document, rows=Rows.all()).worksheet("Matrix").tables[0]
    canonical = pivot.matrix_column(nan)

    assert pivot.row(0).values[canonical.id] == 3


def test_matrix_requirement_indices_skip_blocks() -> None:
    """Requirement indices must follow data sources rather than block positions."""
    document = spreadsheet(
        sheet(
            "Summary",
            table(source=[{"shop": "A"}], columns=(text(id="shop", source="shop"),)),
            title("Gap"),
            _pivot([{"row": "A", "column": "X", "value": 1}]),
        ),
    )

    required = analyze_spreadsheet_requirements(document)

    assert [item.table_index for item in required.execution.data_sources] == [0, 1]


def test_grouped_link_merge_keeps_hyperlink() -> None:
    """Rewriting a merged top-left cell must preserve Link semantics."""
    url = "https://example.com/report"
    document = spreadsheet(
        sheet(
            "Links",
            table(
                source=[{"url": url}, {"url": url}],
                columns=(link(id="url", source="url").grouped(merge=True),),
            ),
        ),
    )

    worksheet = inspect_artifact(render(document, backend="xlsxwriter")).worksheet(
        "Links",
    )

    assert worksheet.cell("A2").hyperlink == url
