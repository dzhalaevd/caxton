import dataclasses
from collections.abc import Iterator

import pytest

from formata import (
    ColumnNotFoundError,
    CyclicColumnError,
    DataSourceIterationError,
    FieldAccessError,
    MissingFieldError,
    SourceEvaluationError,
    decimal,
    field,
    integer,
    path,
    ref,
    sheet,
    spreadsheet,
    table,
    text,
)
from formata._internal.data import coerce_data_source  # noqa: PLC2701
from formata._internal.semantic import SemanticRowEvaluator  # noqa: PLC2701
from formata.core.models import Column
from formata.testing import RowLayout, Rows, inspect_layout


@dataclasses.dataclass
class Address:
    city: str


@dataclasses.dataclass
class Customer:
    name: str
    address: Address


class BrokenRow:
    @property
    def name(self) -> str:
        message = "descriptor failed"
        raise RuntimeError(message)


class AliasedSource:
    def iter_rows(self) -> Iterator[dict[str, str]]:
        yield {"alias": "Ada"}

    def get_value(self, row: dict[str, str], field_name: str) -> object:
        return row[{"name": "alias"}.get(field_name, field_name)]


def _fail_source(_row: object) -> object:
    message = "source failed"
    raise RuntimeError(message)


def _evaluate_directly(row: object, *columns: Column) -> object:
    source = coerce_data_source([row])
    return SemanticRowEvaluator().evaluate_row(source, row, columns, row_index=0)


def _evaluate(rows: object, *columns: Column) -> list[RowLayout]:
    document = spreadsheet(
        sheet("Data", table(rows, *columns, name="data")),
    )
    layout = inspect_layout(document, rows=Rows.all())
    return list(layout.worksheet("Data").table("data").rows)


def test_evaluates_all_source_kinds() -> None:
    rows = [
        {
            "full_name": "Ada",
            "customer": Customer("Ada", Address("London")),
            "price": 120,
            "base_price": 100,
        },
    ]
    label = text("label", source=lambda row: row["full_name"].upper())

    semantic_row = _evaluate(
        rows,
        text("name", source="full_name"),
        text("city", source=path("customer", "address", "city")),
        label,
        decimal("price"),
        decimal("base_price"),
        decimal("delta", source=ref("price") - ref("base_price")),
    )[0]

    assert semantic_row.values == {
        "name": "Ada",
        "city": "London",
        "label": "ADA",
        "price": 120,
        "base_price": 100,
        "delta": 20,
    }


def test_expression_uses_semantic_forward_refs() -> None:
    semantic_row = _evaluate(
        [{"gross_value": 90, "cost_value": 30}],
        decimal("margin", source=ref("gross") - ref("cost")),
        decimal("gross", source="gross_value"),
        decimal("cost", source="cost_value"),
    )[0]

    assert semantic_row["margin"] == 60


def test_field_reads_raw_row_data() -> None:
    semantic_row = _evaluate(
        [{"qty": 3, "unit_price": 20}],
        integer("quantity", source="qty"),
        decimal("unit", source="unit_price"),
        decimal("total", source=field("qty") * field("unit_price")),
    )[0]

    assert semantic_row["total"] == 60


def test_ref_reads_semantic_column() -> None:
    semantic_row = _evaluate(
        [{"qty": 3, "unit_price": 20}],
        integer("quantity", source="qty"),
        decimal("unit", source="unit_price"),
        decimal("total", source=ref("quantity") * ref("unit")),
    )[0]

    assert semantic_row["total"] == 60


def test_unknown_ref_raises_column_error() -> None:
    # Structural validation rejects this earlier, so the evaluator contract is
    # observed directly to prove the diagnostic survives.
    with pytest.raises(ColumnNotFoundError) as captured:
        _evaluate_directly(
            {"amount": 1},
            decimal("amount"),
            decimal("copy", source=ref("nope")),
        )

    error = captured.value
    assert error.column == "nope"
    assert error.path == 'row[0].column["nope"]'


def test_cyclic_ref_raises_cycle_error() -> None:
    with pytest.raises(CyclicColumnError) as captured:
        _evaluate_directly(
            {"value": 1},
            decimal("left", source=ref("right")),
            decimal("right", source=ref("left")),
        )

    error = captured.value
    assert error.column == "left"
    assert error.row_index == 0
    assert "Cyclic" in error.message


def test_evaluation_stays_lazy_for_generator() -> None:
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"name": "Ada"}

    document = spreadsheet(
        sheet("Data", table(rows(), text("name"), name="data")),
    )

    structure = inspect_layout(document)
    assert not visited
    assert structure.worksheet("Data").table("data").rows == ()

    sampled = inspect_layout(document, rows=Rows.sample(1))
    assert sampled.worksheet("Data").table("data").row(0)["name"] == "Ada"
    assert visited


def test_iteration_failure_has_source_context() -> None:
    failure = RuntimeError("database cursor failed")

    def rows() -> Iterator[dict[str, str]]:
        yield {"name": "Ada"}
        raise failure

    with pytest.raises(DataSourceIterationError) as captured:
        _evaluate(rows(), text("name"))

    error = captured.value
    assert error.row_index == 1
    assert error.context == {
        "exception_type": "RuntimeError",
        "row_index": 1,
        "source_type": "IterableDataSource",
    }
    assert error.__cause__ is failure


def test_cell_value_validation_is_lazy() -> None:
    visited = False

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visited
        visited = True
        yield {"value": ["mutable"]}

    document = spreadsheet(
        sheet("Data", table(rows(), text("value"), name="data")),
    )

    inspect_layout(document)
    assert not visited
    with pytest.raises(SourceEvaluationError, match="value"):
        inspect_layout(document, rows=Rows.all())
    assert visited


def test_custom_source_controls_field_access() -> None:
    semantic_row = _evaluate(AliasedSource(), text("name"))[0]

    assert semantic_row["name"] == "Ada"


def test_missing_field_has_semantic_row_context() -> None:
    with pytest.raises(MissingFieldError) as captured:
        _evaluate([{"name": "Ada"}], text("email"))

    error = captured.value
    assert error.field == "email"
    assert error.row_index == 0
    assert error.path == 'row[0].column["email"]'
    assert error.context["row_type"] == "dict"
    assert isinstance(error.__cause__, KeyError)


def test_nested_missing_field_has_context() -> None:
    with pytest.raises(MissingFieldError) as captured:
        _evaluate(
            [{"customer": {"name": "Ada"}}],
            text("city", source=path("customer", "address", "city")),
        )

    error = captured.value
    assert error.field == "address"
    assert error.path == 'row[0].column["city"]'


def test_expression_keeps_dependency_error_path() -> None:
    with pytest.raises(MissingFieldError) as captured:
        _evaluate(
            [{"cost": 30}],
            decimal("margin", source=ref("gross") - ref("cost")),
            decimal("gross"),
            decimal("cost"),
        )

    assert captured.value.path == 'row[0].column["gross"]'


def test_attribute_failure_keeps_original_cause() -> None:
    with pytest.raises(FieldAccessError) as captured:
        _evaluate(BrokenRow(), text("name"))

    error = captured.value
    assert error.row_index == 0
    assert error.path == 'row[0].column["name"]'
    assert isinstance(error.__cause__, RuntimeError)


@pytest.mark.parametrize(
    ("columns", "failed_column", "exception_type"),
    [
        ((text("label", source=_fail_source),), "label", RuntimeError),
        (
            (
                decimal("value"),
                decimal("denominator"),
                decimal("ratio", source=ref("value") / ref("denominator")),
            ),
            "ratio",
            ZeroDivisionError,
        ),
    ],
)
def test_source_failures_have_one_public_error(
    columns: tuple[Column, ...],
    failed_column: str,
    exception_type: type[Exception],
) -> None:
    with pytest.raises(SourceEvaluationError) as captured:
        _evaluate([{"value": 10, "denominator": 0}], *columns)

    error = captured.value
    assert error.column == failed_column
    assert error.row_index == 0
    assert error.path == f'row[0].column["{failed_column}"]'
    assert isinstance(error.__cause__, exception_type)
