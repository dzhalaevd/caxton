import dataclasses
from collections.abc import Callable, Iterator

import pytest

from formata import decimal, field, money, path, sheet, spreadsheet, table, text
from formata.core.formatting import Alignment, money_format
from formata.core.models import Column
from formata.testing import (
    ColumnSpec,
    Difference,
    DifferenceKind,
    Rows,
    RowsMode,
    SemanticTypeSpec,
    SourceKind,
    SourceSpec,
    SpreadsheetAssertionError,
    SpreadsheetSpec,
    TableSpec,
    WorksheetSpec,
    assert_spreadsheet_equal,
    inspect_layout,
    inspect_spec,
)


def test_inspection_does_not_consume_rows() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"revenue": 100}

    document = spreadsheet(
        sheet(
            "Summary",
            table(
                rows(),
                money("revenue")
                .title("Revenue")
                .align("right")
                .width(18)
                .format(money_format(currency="USD")),
                name="sales",
                anchor="D10",
            ),
        ),
        metadata={"locale": "en"},
    )

    inspected = inspect_spec(document)
    column = inspected.worksheet("Summary").table("sales").column("revenue")

    assert column == ColumnSpec(
        id="revenue",
        title="Revenue",
        semantic_type=SemanticTypeSpec(
            name="money",
            parameters={"currency": None},
        ),
        source=SourceSpec(SourceKind.FIELD, "revenue"),
        alignment=Alignment.RIGHT,
        width=18,
        display_format=money_format(currency="USD"),
    )
    assert inspected.metadata == {"locale": "en"}
    assert not visited


def test_value_objects_expose_declaration_order() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table([], text("name"), money("revenue"), name="sales"),
        ),
    )

    inspected = inspect_spec(document)
    sales = inspected.worksheet("Summary").table("sales")

    assert sales.column_ids == ("name", "revenue")
    assert inspected == SpreadsheetSpec(
        worksheets=(
            WorksheetSpec(
                name="Summary",
                tables=(
                    TableSpec(
                        name="sales",
                        anchor=None,
                        columns=sales.columns,
                    ),
                ),
            ),
        ),
        metadata={},
    )


@pytest.mark.parametrize(
    ("select", "message"),
    [
        (
            lambda spec: spec.worksheet("Missing"),
            "Worksheet 'Missing' was not found",
        ),
        (
            lambda spec: spec.worksheet("Summary").table("missing"),
            "Table 'missing' was not found in worksheet 'Summary'",
        ),
        (
            lambda spec: spec.worksheet("Summary").table("sales").column("missing"),
            "Column 'missing' was not found in table 'sales'",
        ),
    ],
)
def test_missing_selector_has_focused_error(
    select: Callable[[SpreadsheetSpec], object],
    message: str,
) -> None:
    document = spreadsheet(
        sheet("Summary", table([], text("name"), name="sales")),
    )

    with pytest.raises(LookupError, match=message):
        select(inspect_spec(document))


def test_inspection_values_are_immutable() -> None:
    worksheets = [WorksheetSpec(name="Summary", tables=())]
    metadata = {"labels": ["draft"]}
    inspected = SpreadsheetSpec(
        worksheets=worksheets,
        metadata=metadata,
    )
    worksheets.clear()
    metadata["labels"].append("final")

    with pytest.raises(dataclasses.FrozenInstanceError):
        inspected.worksheets = ()  # type: ignore[misc]
    assert len(inspected.worksheets) == 1
    assert inspected.metadata["labels"] == ("draft",)


def test_equal_spreadsheets_do_not_consume_rows() -> None:
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"name": "Ada"}

    actual = spreadsheet(sheet("People", table(rows(), text("name"))))
    expected = spreadsheet(sheet("People", table([], text("name"))))

    assert_spreadsheet_equal(actual, expected)
    assert not visited


def test_spreadsheet_difference_has_semantic_path() -> None:
    actual = spreadsheet(
        sheet(
            "Sales",
            table([], money("revenue").title("Actual"), name="sales"),
        ),
    )
    expected = spreadsheet(
        sheet(
            "Sales",
            table([], money("revenue").title("Expected"), name="sales"),
        ),
    )

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(actual, expected)

    assert captured.value.differences == (
        Difference(
            path="worksheet['Sales'].table['sales'].column['revenue'].title",
            kind=DifferenceKind.VALUE,
            expected="Expected",
            actual="Actual",
        ),
    )
    assert "expected: 'Expected'" in str(captured.value)
    assert "actual:   'Actual'" in str(captured.value)


def test_missing_and_unexpected_differences() -> None:
    actual = spreadsheet(sheet("Actual"))
    expected = spreadsheet(sheet("Expected"))

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(actual, expected)

    assert [difference.kind for difference in captured.value.differences] == [
        DifferenceKind.MISSING,
        DifferenceKind.UNEXPECTED,
    ]
    assert [difference.path for difference in captured.value.differences] == [
        "worksheet['Expected']",
        "worksheet['Actual']",
    ]


def test_spreadsheet_order_can_be_ignored() -> None:
    first = spreadsheet(sheet("A"), sheet("B"))
    second = spreadsheet(sheet("B"), sheet("A"))

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(first, second)

    assert captured.value.differences == (
        Difference(
            path="worksheets",
            kind=DifferenceKind.ORDER,
            expected=("B", "A"),
            actual=("A", "B"),
        ),
    )
    assert_spreadsheet_equal(first, second, check_order=False)


def test_metadata_check_can_be_disabled() -> None:
    actual = spreadsheet(metadata={"locale": "ru"})
    expected = spreadsheet(metadata={"locale": "en"})

    with pytest.raises(SpreadsheetAssertionError, match=r"metadata\['locale'\]"):
        assert_spreadsheet_equal(actual, expected)

    assert_spreadsheet_equal(actual, expected, check_metadata=False)


@pytest.mark.parametrize(
    ("actual_column", "expected_column"),
    [
        (text("value", source="actual"), text("value", source="expected")),
        (
            text("value", source=path("actual", "name")),
            text("value", source=path("expected", "name")),
        ),
        (
            decimal("value", source=field("left") + 1),
            decimal("value", source=field("right") + 1),
        ),
    ],
)
def test_column_source_difference(
    actual_column: Column,
    expected_column: Column,
) -> None:
    actual = spreadsheet(sheet("Data", table([], actual_column, name="data")))
    expected = spreadsheet(sheet("Data", table([], expected_column, name="data")))

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(actual, expected)

    assert captured.value.differences[0].path.endswith(".source")


def test_semantic_type_parameter_difference() -> None:
    actual = spreadsheet(
        sheet("Data", table([], money("amount", currency="USD"), name="data")),
    )
    expected = spreadsheet(
        sheet("Data", table([], money("amount", currency="EUR"), name="data")),
    )

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(actual, expected)

    difference = captured.value.differences[0]
    assert difference.path.endswith(".semantic_type")
    assert isinstance(difference.actual, SemanticTypeSpec)
    assert isinstance(difference.expected, SemanticTypeSpec)
    assert difference.actual.parameters == {"currency": "USD"}
    assert difference.expected.parameters == {"currency": "EUR"}


def test_callable_sources_use_callable_identity() -> None:
    def first(row: object) -> object:
        return row

    def second(row: object) -> object:
        return row

    shared = spreadsheet(sheet("Data", table([], text("value", source=first))))
    same = spreadsheet(sheet("Data", table([], text("value", source=first))))
    different = spreadsheet(sheet("Data", table([], text("value", source=second))))

    assert_spreadsheet_equal(shared, same)
    with pytest.raises(SpreadsheetAssertionError):
        assert_spreadsheet_equal(shared, different)


def test_callable_identity_is_deterministic() -> None:
    def make_source(offset: int) -> Callable[[dict[str, int]], int]:
        return lambda row: row["value"] + offset

    first = inspect_spec(
        spreadsheet(sheet("Data", table([], text("value", source=make_source(1))))),
    )
    equivalent = inspect_spec(
        spreadsheet(sheet("Data", table([], text("value", source=make_source(1))))),
    )
    different = inspect_spec(
        spreadsheet(sheet("Data", table([], text("value", source=make_source(2))))),
    )

    first_source = first.worksheet("Data").tables[0].columns[0].source
    equivalent_source = equivalent.worksheet("Data").tables[0].columns[0].source
    different_source = different.worksheet("Data").tables[0].columns[0].source
    assert first_source == equivalent_source
    assert first_source != different_source


@pytest.mark.parametrize("duplicate_level", ["worksheet", "table", "column"])
def test_duplicate_identities_use_positions(
    duplicate_level: str,
) -> None:
    if duplicate_level == "worksheet":
        actual = spreadsheet(
            sheet("Same", table([], text("value").title("Actual"))),
            sheet("Same", table([], text("value").title("Shared"))),
        )
        expected = spreadsheet(
            sheet("Same", table([], text("value").title("Expected"))),
            sheet("Same", table([], text("value").title("Shared"))),
        )
    elif duplicate_level == "table":
        actual = spreadsheet(
            sheet(
                "Data",
                table([], text("value").title("Actual"), name="same"),
                table([], text("value").title("Shared"), name="same"),
            ),
        )
        expected = spreadsheet(
            sheet(
                "Data",
                table([], text("value").title("Expected"), name="same"),
                table([], text("value").title("Shared"), name="same"),
            ),
        )
    else:
        actual = spreadsheet(
            sheet(
                "Data",
                table(
                    [],
                    text("same").title("Actual"),
                    text("same").title("Shared"),
                    name="data",
                ),
            ),
        )
        expected = spreadsheet(
            sheet(
                "Data",
                table(
                    [],
                    text("same").title("Expected"),
                    text("same").title("Shared"),
                    name="data",
                ),
            ),
        )

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(actual, expected)

    assert len(captured.value.differences) == 1
    assert captured.value.differences[0].actual == "Actual"
    assert captured.value.differences[0].expected == "Expected"


def test_difference_snapshots_mutable_payloads() -> None:
    actual = ["draft"]
    difference = Difference(
        path="metadata['labels']",
        kind=DifferenceKind.VALUE,
        expected=("final",),
        actual=actual,
    )
    actual.append("changed")

    assert difference.actual == ("draft",)


def test_layout_row_scopes_are_bounded() -> None:
    document = spreadsheet(
        sheet(
            "Data",
            table(
                [{"value": 1}, {"value": 2}, {"value": 3}],
                decimal("value"),
                name="data",
            ),
        ),
    )

    structure = inspect_layout(document)
    sample = inspect_layout(document, rows=Rows.sample(2))
    complete = inspect_layout(document, rows=Rows.all())

    assert not structure.worksheet("Data").table("data").rows
    assert [row["value"] for row in sample.worksheet("Data").table("data").rows] == [
        1,
        2,
    ]
    assert len(complete.worksheet("Data").table("data").rows) == 3


@pytest.mark.parametrize(
    "make_rows",
    [
        lambda: Rows.sample(0),
        lambda: Rows.sample(limit=True),
        lambda: Rows(RowsMode.NONE, limit=1),
        lambda: Rows(RowsMode.ALL, limit=1),
    ],
)
def test_invalid_row_scopes_are_rejected(make_rows: Callable[[], Rows]) -> None:
    with pytest.raises(ValueError, match=r"[Rr]ow limit"):
        make_rows()
