import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from caxton import (
    UnsupportedFeatureError,
    ValidationError,
    col,
    decimal,
    field,
    ref,
    render,
    sheet,
    sheet_ref,
    spreadsheet,
    table,
    table_ref,
    validate,
    write as write_spreadsheet,
)
from caxton.core.models import (
    CellReference,
    FormulaBinary,
    RangeReference,
)
from caxton.testing import (
    Rows,
    SpreadsheetAssertionError,
    assert_spreadsheet_equal,
    inspect_artifact,
    inspect_layout,
    inspect_spec,
)


def test_formula_references_are_immutable() -> None:  # noqa: WPS218
    base = decimal("delta")
    formula_column = base.formula(
        col("price") - col("base_price").absolute(),
    )
    named_range = table_ref("sales").column("price")
    cross_sheet_cell = (
        sheet_ref("Rates").table("rates").column("rate").cell(0).absolute()
    )
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                [{"price": 10, "base_price": 8}],
                decimal("price"),
                decimal("base_price"),
                formula_column,
                name="sales",
            ),
        ),
    )

    inspected = inspect_spec(document).worksheet("Sales").table("sales")

    assert base.excel_formula is None
    assert isinstance(formula_column.excel_formula, FormulaBinary)
    assert formula_column.source is None
    assert inspected.column("delta").source is None
    assert inspected.column("delta").formula is not None
    assert isinstance(named_range, RangeReference)
    assert isinstance(cross_sheet_cell, CellReference)
    assert cross_sheet_cell.sheet_name == "Rates"
    assert cross_sheet_cell.table_name == "rates"
    assert cross_sheet_cell.column_id == "rate"
    assert cross_sheet_cell.row_index == 0
    assert cross_sheet_cell.column_absolute
    assert cross_sheet_cell.row_absolute
    with pytest.raises(dataclasses.FrozenInstanceError):
        cross_sheet_cell.row_index = 1  # type: ignore[misc]


def test_formula_construction_is_separate() -> None:
    with pytest.raises(TypeError, match="Python row expressions"):
        decimal("delta").formula(
            field("price") - field("base_price"),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="both"):
        decimal("delta", source="value", formula=col("price"))
    with pytest.raises(TypeError, match="Unsupported formula literal"):
        decimal("delta").formula([1])  # type: ignore[arg-type]


def test_semantic_diff_observes_formula_changes() -> None:
    actual = spreadsheet(
        sheet(
            "Data",
            table(
                [{}],
                decimal("left"),
                decimal("right"),
                decimal("result", formula=col("left") + 1),
            ),
        ),
    )
    expected = spreadsheet(
        sheet(
            "Data",
            table(
                [{}],
                decimal("left"),
                decimal("right"),
                decimal("result", formula=col("right") + 1),
            ),
        ),
    )

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(actual, expected)

    assert captured.value.differences[0].path.endswith(".formula")


def test_validation_reports_missing_refs_lazily() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"value": 1}

    document = spreadsheet(
        sheet(
            "Summary",
            table(
                rows(),
                decimal("value"),
                decimal("missing_local", formula=col("unknown")),
                decimal(
                    "missing_sheet",
                    formula=(
                        sheet_ref("Absent").table("rates").column("value").cell(0)
                    ),
                ),
                decimal(
                    "missing_table",
                    formula=table_ref("absent").column("value"),
                ),
                name="summary",
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert not visited
    assert {issue.code for issue in captured.value.issues} == {
        "ColumnNotFoundError",
        "table_not_found",
        "worksheet_not_found",
    }


def test_validation_rejects_missing_semantic_row() -> None:
    document = spreadsheet(
        sheet(
            "Rates",
            table([{"value": 1}], decimal("value"), name="rates"),
        ),
        sheet(
            "Summary",
            table(
                [{}],
                decimal(
                    "value",
                    formula=table_ref("rates").column("value").cell(1),
                ),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert captured.value.issues[0].code == "row_not_found"


def test_validation_detects_formula_cycles() -> None:
    document = spreadsheet(
        sheet(
            "Left",
            table(
                [{}],
                decimal(
                    "value",
                    formula=(sheet_ref("Right").table("right").column("value").cell(0)),
                ),
                name="left",
            ),
        ),
        sheet(
            "Right",
            table(
                [{}],
                decimal(
                    "value",
                    formula=(sheet_ref("Left").table("left").column("value").cell(0)),
                ),
                name="right",
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    issue = next(
        issue for issue in captured.value.issues if issue.code == "CyclicReferenceError"
    )
    expected_cycle = (
        'worksheet["Left"].table[0].column["value"].formula',
        'worksheet["Right"].table[0].column["value"].formula',
        'worksheet["Left"].table[0].column["value"].formula',
    )
    assert issue.context == {"column": "value", "cycle": expected_cycle}


def test_direct_formula_cycle_is_reported_once() -> None:
    document = spreadsheet(
        sheet(
            "Cycles",
            table(
                [{}],
                decimal("value", formula=col("value") + col("value")),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    cycle_issues = tuple(
        issue for issue in captured.value.issues if issue.code == "CyclicReferenceError"
    )
    assert len(cycle_issues) == 1
    assert cycle_issues[0].context["column"] == "value"


def test_table_reference_cycle_reports_path() -> None:
    document = spreadsheet(
        sheet(
            "Cycles",
            table(
                [{}],
                decimal(
                    "value",
                    formula=table_ref("second").column("value"),
                ),
                name="first",
            ),
            table(
                [{}],
                decimal(
                    "value",
                    formula=table_ref("third").column("value"),
                ),
                name="second",
            ),
            table(
                [{}],
                decimal(
                    "value",
                    formula=table_ref("first").column("value"),
                ),
                name="third",
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    issue = next(
        issue for issue in captured.value.issues if issue.code == "CyclicReferenceError"
    )
    prefix = 'worksheet["Cycles"].table'
    expected_cycle = (
        f'{prefix}[0].column["value"].formula',
        f'{prefix}[1].column["value"].formula',
        f'{prefix}[2].column["value"].formula',
        f'{prefix}[0].column["value"].formula',
    )
    assert issue.context == {"column": "value", "cycle": expected_cycle}


def test_python_expr_rejects_formula_column() -> None:
    document = spreadsheet(
        sheet(
            "Mixed",
            table(
                [{"value": 1}],
                decimal("value"),
                decimal("artifact_value", formula=col("value") + 1),
                decimal("python_value", source=ref("artifact_value") + 1),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert captured.value.issues[0].code == "formula_in_python_expression"


def test_layout_resolves_formula_references() -> None:
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                [{"price": 10, "base_price": 8}],
                decimal("price").titled("Unit price"),
                decimal("base_price"),
                decimal(
                    "delta",
                    formula=col("price") - col("base_price").absolute(row=False),
                ),
                name="sales",
                anchor="D10",
            ),
        ),
        sheet(
            "Summary",
            table(
                [{}],
                decimal(
                    "first_price",
                    formula=(
                        sheet_ref("Sales")
                        .table("sales")
                        .column("price")
                        .cell(0)
                        .absolute()
                    ),
                ),
                decimal(
                    "all_prices",
                    formula=table_ref("sales").column("price"),
                ),
                decimal(
                    "fixed_prices",
                    formula=table_ref("sales").column("price").absolute(),
                ),
                name="summary",
            ),
        ),
    )

    layout = inspect_layout(document, rows=Rows.all())

    sales = layout.worksheet("Sales")
    assert sales.cell("F11").value is None
    assert sales.cell("F11").formula == "=D11-$E11"
    summary = layout.worksheet("Summary")
    assert summary.cell("A2").formula == "='Sales'!$D$11"
    assert summary.cell("B2").formula == "=sales[Unit price]"
    assert summary.cell("C2").formula == "='Sales'!$D$11:$D$11"


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_xlsx_renderers_write_resolved_formulas(backend: str) -> None:
    document = spreadsheet(
        sheet(
            "Sales Data",
            table(
                [{"price": 10, "base_price": 8}],
                decimal("price").titled("Unit price"),
                decimal("base_price"),
                decimal(
                    "delta",
                    formula=col("price") - col("base_price").absolute(row=False),
                ),
                name="sales",
                anchor="D10",
            ),
        ),
        sheet(
            "Summary",
            table(
                [{}],
                decimal(
                    "first_price",
                    formula=(
                        sheet_ref("Sales Data")
                        .table("sales")
                        .column("price")
                        .cell(0)
                        .absolute()
                    ),
                ),
                decimal(
                    "all_prices",
                    formula=table_ref("sales").column("price"),
                ),
                name="summary",
            ),
        ),
    )

    artifact = inspect_artifact(render(document, backend=backend))

    assert artifact.worksheet("Sales Data").cell("F11").formula == "=D11-$E11"
    summary = artifact.worksheet("Summary")
    assert summary.cell("A2").formula == "='Sales Data'!$D$11"
    assert summary.cell("B2").formula == "=sales[Unit price]"


def test_unknown_range_size_fails_before_write(tmp_path: Path) -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"price": 10}

    document = spreadsheet(
        sheet(
            "Sales",
            table(rows(), decimal("price"), name="sales"),
        ),
        sheet(
            "Summary",
            table(
                [{}],
                decimal(
                    "prices",
                    formula=table_ref("sales").column("price"),
                ),
            ),
        ),
    )
    target = tmp_path / "report.xlsx"

    with pytest.raises(UnsupportedFeatureError) as captured:
        write_spreadsheet(document, target)

    assert captured.value.context == {
        "table": "sales",
        "reason": "unknown_row_count",
    }
    assert not visited
    assert not target.exists()
