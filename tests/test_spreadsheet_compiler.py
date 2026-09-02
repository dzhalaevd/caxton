from collections.abc import Iterator

import pytest

from caxton import (
    DataSourceConsumedError,
    ValidationError,
    decimal,
    money,
    ref,
    sheet,
    spreadsheet,
    table,
    text,
    validate,
)
from caxton.core.formatting import Alignment, money_format
from caxton.core.ir import (
    SPREADSHEET_IR_VERSION,
    SpreadsheetRowIR,
)
from caxton.testing import Rows, assert_spreadsheet_equal, inspect_layout, inspect_spec


def test_validation_collects_schema_issues() -> None:
    rows = [{"amount": 10}]
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=rows,
                columns=(
                    decimal(id="amount", source="amount"),
                    decimal(id="amount", source="amount"),
                    decimal(id="delta", source=ref("missing") - ref("amount")),
                ),
                name="sales",
                anchor="invalid",
            ),
        ),
        sheet(
            "Sales",
            table(source=rows, columns=(text(id="name", source="name"),), name="sales"),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    issues = captured.value.issues
    assert {issue.code for issue in issues} == {
        "ColumnNotFoundError",
        "DuplicateColumnError",
        "duplicate_table",
        "duplicate_worksheet",
        "invalid_anchor",
    }


def test_transform_retains_column_dependencies() -> None:
    document = spreadsheet(
        sheet(
            "Data",
            table(
                source=[],
                columns=(
                    text(
                        id="status",
                        source=ref("missing").transform(str),
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert {issue.code for issue in captured.value.issues} == {
        "ColumnNotFoundError",
    }


def test_validation_uses_xlsx_name_identity() -> None:
    document = spreadsheet(
        sheet(
            "Data",
            table(
                source=[{"value": 1}],
                columns=(text(id="value", source="value"),),
                name="Sales",
            ),
        ),
        sheet(
            "data",
            table(
                source=[{"value": 2}],
                columns=(text(id="value", source="value"),),
                name="sales",
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert {issue.code for issue in captured.value.issues} == {
        "duplicate_table",
        "duplicate_worksheet",
    }


def test_validation_is_lazy_and_detects_cycles() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"value": 1}

    document = spreadsheet(
        sheet(
            "Cycles",
            table(
                source=rows(),
                columns=(
                    decimal(id="left", source=ref("right") + 1),
                    decimal(id="right", source=ref("left") + 1),
                ),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert not visited
    assert "CyclicReferenceError" in {issue.code for issue in captured.value.issues}


def test_direct_reference_cycle_reports_path() -> None:
    document = spreadsheet(
        sheet(
            "Cycles",
            table(
                source=[{"value": 1}],
                columns=(decimal(id="value", source=ref("value")),),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    issue = next(
        issue for issue in captured.value.issues if issue.code == "CyclicReferenceError"
    )
    reference_path = 'worksheet["Cycles"].table[0].column["value"].source'
    assert issue.context == {
        "column": "value",
        "cycle": (reference_path, reference_path),
    }


def test_indirect_reference_cycle_reports_path() -> None:
    document = spreadsheet(
        sheet(
            "Cycles",
            table(
                source=[{"value": 1}],
                columns=(
                    decimal(id="first", source=ref("second")),
                    decimal(id="second", source=ref("third")),
                    decimal(id="third", source=ref("first")),
                ),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    issue = next(
        issue for issue in captured.value.issues if issue.code == "CyclicReferenceError"
    )
    prefix = 'worksheet["Cycles"].table[0].column'
    expected_cycle = (
        f'{prefix}["first"].source',
        f'{prefix}["second"].source',
        f'{prefix}["third"].source',
        f'{prefix}["first"].source',
    )
    assert issue.context == {"column": "first", "cycle": expected_cycle}


def test_later_tables_flow_below_predecessor() -> None:
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=[{"first": "a"}, {"first": "b"}],
                columns=(text(id="first", source="first"),),
            ),
            table(
                source=[{"second": "c"}],
                columns=(text(id="second", source="second"),),
                name="second",
            ),
        ),
    )

    validate(document)
    layout = inspect_layout(document)

    assert layout.worksheet("Sales").table("second").anchor == "A4"


def test_overlapping_explicit_blocks_are_rejected() -> None:
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=[{"first": "a"}],
                columns=(text(id="first", source="first"),),
                anchor="A1",
            ),
            table(
                source=[{"second": "c"}],
                columns=(text(id="second", source="second"),),
                anchor="A2",
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert captured.value.issues[0].code == "block_overlap"


def test_compiler_builds_resolved_layout() -> None:  # noqa: WPS218
    gross = (
        money(id="gross", source="gross_value", currency="USD")
        .titled("Gross")
        .align("right")
        .width(18)
        .format(money_format(currency="USD"))
    )
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=[{"gross_value": 90, "cost_value": 30}],
                columns=(
                    gross,
                    money(id="cost", source="cost_value"),
                    decimal(id="margin", source=ref("gross") - ref("cost")),
                ),
                name="sales",
                anchor="d10",
            ),
        ),
        metadata={"locale": "en"},
    )

    layout = inspect_layout(document, rows=Rows.sample(1))
    compiled_table = layout.worksheet("Sales").table("sales")
    gross_column = compiled_table.column("gross")

    assert layout.version == SPREADSHEET_IR_VERSION
    assert layout.metadata == {"locale": "en"}
    assert compiled_table.name == "sales"
    assert compiled_table.anchor == "D10"
    assert gross_column.offset == 0
    assert gross_column.title == "Gross"
    assert gross_column.semantic_type.name == "money"
    assert gross_column.semantic_type.parameters == {"currency": "USD"}
    assert gross_column.alignment is Alignment.RIGHT
    assert gross_column.width == 18
    assert compiled_table.row(0).values == {
        "gross": 90,
        "cost": 30,
        "margin": 60,
    }
    worksheet = layout.worksheet("Sales")
    assert worksheet.cell("D10").value == "Gross"
    assert worksheet.cell("F11").value == 60
    with pytest.raises(TypeError):
        layout.metadata["locale"] = "ru"  # type: ignore[index]


def test_compilation_preserves_the_semantic_model() -> None:
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=[{"gross": 100, "cost": 40}],
                columns=(
                    decimal(id="gross", source="gross"),
                    decimal(id="cost", source="cost"),
                    decimal(id="margin", source=ref("gross") - ref("cost")),
                ),
                name="sales",
            ),
        ),
    )
    before_compilation = inspect_spec(document)

    inspect_layout(document, rows=Rows.all())

    assert_spreadsheet_equal(document, before_compilation)


def test_compiler_preserves_lazy_one_shot_rows() -> None:
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"name": "Ada"}

    document = spreadsheet(
        sheet(
            "People",
            table(source=rows(), columns=(text(id="name", source="name"),)),
        )
    )

    structure = inspect_layout(document)

    assert not visited
    assert not structure.worksheet("People").tables[0].rows

    inspected = inspect_layout(document, rows=Rows.all())
    assert inspected.worksheet("People").tables[0].row(0).values == {"name": "Ada"}
    assert visited
    with pytest.raises(DataSourceConsumedError):
        inspect_layout(document, rows=Rows.all())


def test_ir_row_values_are_snapshots() -> None:
    values = ["Ada"]
    row = SpreadsheetRowIR(index=0, values=values)
    values.append("Grace")

    assert row.values == ("Ada",)
    with pytest.raises(TypeError, match="Unsupported cell value"):
        SpreadsheetRowIR(index=0, values=(["mutable"],))  # type: ignore[arg-type]
