import inspect
from collections.abc import Callable, Iterator

import pytest

import caxton as caxton_package
from caxton import (
    CaxtonTypeError,
    CaxtonValueError,
    api as caxton_api,
    boolean,
    col,
    date,
    datetime,
    decimal,
    duration,
    field,
    integer,
    link,
    matrix,
    money,
    percentage,
    sheet,
    spreadsheet,
    table,
    text,
    time,
)
from caxton.core.models import (
    Column,
    FieldRef,
    SpreadsheetDocument,
    SpreadsheetTable,
    TableData,
    Worksheet,
)
from caxton.core.types import Money, Text
from caxton.testing import assert_spreadsheet_equal


class _EmptySource:
    def iter_rows(self) -> Iterator[object]:
        return iter(())

    def get_value(self, _row: object, _field: str) -> object:
        return object()


def test_table_dsl_matches_direct_semantic_model() -> None:
    visited = False

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visited
        visited = True
        yield {"employee_id": "A-1", "gross": 100}

    actual = spreadsheet(
        sheet(
            "Sales",
            table(
                source=rows(),
                columns=(
                    text(
                        id="person_id",
                        source=field("employee_id"),
                        title="Employee",
                    ),
                    money(
                        id="revenue",
                        source=field("gross"),
                        currency="USD",
                    ),
                ),
                name="sales",
            ),
        ),
        metadata={"locale": "en"},
    )
    expected = SpreadsheetDocument(
        worksheets=(
            Worksheet(
                name="Sales",
                blocks=(
                    SpreadsheetTable(
                        data=TableData(
                            source=_EmptySource(),
                            columns=(
                                Column(
                                    id="person_id",
                                    semantic_type=Text(),
                                    source=FieldRef("employee_id"),
                                    title="Employee",
                                ),
                                Column(
                                    id="revenue",
                                    semantic_type=Money(currency="USD"),
                                    source=FieldRef("gross"),
                                ),
                            ),
                        ),
                        name="sales",
                    ),
                ),
            ),
        ),
        metadata={"locale": "en"},
    )

    assert_spreadsheet_equal(actual, expected)
    assert not visited


def test_column_requires_explicit_value_source() -> None:
    with pytest.raises(
        CaxtonValueError,
        match="Column 'name' requires either a Python source or an Excel formula",
    ):
        text(id="name", title="Name")


def test_string_source_defaults_semantic_id() -> None:
    result = text(source="shop", title="Shop")

    assert result.id == "shop"
    assert isinstance(result.source, FieldRef)
    assert result.source.name == "shop"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source": field("shop")},
        {"formula": col("shop")},
    ],
)
def test_non_string_source_requires_explicit_id(kwargs: dict[str, object]) -> None:
    with pytest.raises(
        CaxtonValueError,
        match="Column id is required unless source is a field name",
    ):
        text(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "factory",
    [
        boolean,
        date,
        datetime,
        decimal,
        duration,
        integer,
        link,
        money,
        percentage,
        text,
        time,
    ],
)
def test_flat_factories_create_columns(
    factory: Callable[..., Column],
) -> None:
    result = factory(id="value", source=field("raw_value"), title="Value")

    assert result.id == "value"
    assert isinstance(result.source, FieldRef)
    assert result.source.name == "raw_value"
    assert result.title == "Value"


@pytest.mark.parametrize(
    "factory",
    [
        boolean,
        date,
        datetime,
        decimal,
        duration,
        integer,
        link,
        money,
        percentage,
        text,
        time,
    ],
)
def test_flat_factory_signatures_match(factory: Callable[..., Column]) -> None:
    parameters = inspect.signature(factory).parameters
    assert {"id", "source", "title", "formula", "style"} <= set(parameters)
    assert parameters["id"].default is None


def test_formula_column_needs_no_python_source() -> None:
    result = decimal(id="delta", formula=col("price") - col("cost"))

    assert result.source is None
    assert result.excel_formula is not None


@pytest.mark.parametrize("kwargs", [{}, {"source": []}, {"columns": ()}])
def test_table_requires_source_and_columns(kwargs: dict[str, object]) -> None:
    with pytest.raises(TypeError, match="required keyword-only argument"):
        table(**kwargs)  # type: ignore[arg-type]


def test_table_rejects_positional_construction() -> None:
    name = text(id="name", source=field("name"))

    with pytest.raises(TypeError):
        table([], name)  # type: ignore[call-arg, arg-type]


def test_table_rejects_single_column() -> None:
    with pytest.raises(
        CaxtonTypeError,
        match="Table columns must be a sequence of Column values",
    ):
        table(source=[], columns=text(source="name"))  # type: ignore[arg-type]


def test_matrix_uses_keyword_source() -> None:
    result = matrix(
        source=[],
        row="shop",
        column="month",
        value=decimal(source="amount"),
    )

    assert result.row_dimensions[0].id == "shop"

    with pytest.raises(TypeError):
        matrix(  # type: ignore[call-arg]
            [],
            row="shop",
            column="month",
            value=decimal(source="amount"),
        )


def test_column_rejects_non_string_id() -> None:
    with pytest.raises(CaxtonTypeError, match="Column id must be a string"):
        text(id=123, source="name")  # type: ignore[arg-type]


def test_column_factories_are_flat_public_exports() -> None:
    factory_names = {
        "boolean",
        "date",
        "datetime",
        "decimal",
        "duration",
        "integer",
        "link",
        "money",
        "percentage",
        "text",
        "time",
    }

    for facade in (caxton_package, caxton_api):
        assert "column" not in facade.__all__
        assert factory_names.issubset(facade.__all__)
        assert all(callable(getattr(facade, name)) for name in factory_names)
