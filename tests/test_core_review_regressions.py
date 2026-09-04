"""Regressions for the findings recorded in code_review_core.md."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from typing import ClassVar

import pytest

from caxton import (
    CaxtonTypeError,
    CaxtonValueError,
    DefaultRowAccessor,
    RenderResult,
    TemplateRef,
    col,
    decimal,
    decimal_format,
    image,
    integer,
    money,
    money_format,
    render,
    repeat,
    sheet,
    slot,
    spreadsheet,
    table,
    text,
)
from caxton.api import xlsx
from caxton.core.formatting import CustomFormat
from caxton.core.ir import (
    CellAddress,
    ResolvedFormula,
    ResolvedFormulaNode,
    RowStream,
    SpreadsheetRowIR,
    SpreadsheetTableIR,
)
from caxton.core.models import Column
from caxton.core.models.columns import make_column
from caxton.core.types import Money, SemanticType
from caxton.errors import (
    InvalidOperationError,
    MissingFieldError,
    Notification,
    RenderError,
    ShapeError,
)

_ROWS = ({"amount": 3},)


class Rating(SemanticType):
    """User-defined semantic type used to prove the extension contract."""

    name: ClassVar[str] = "rating"
    numeric: ClassVar[bool] = True

    def default_format(self) -> CustomFormat:
        return CustomFormat(name="rating", pattern="0.0")


@dataclasses.dataclass
class _CursorSource:
    rows: tuple[dict[str, object], ...]
    get_value: ClassVar[DefaultRowAccessor] = DefaultRowAccessor()

    def iter_rows(self) -> Iterator[dict[str, object]]:
        return iter(self.rows)


def _row_stream(count: int) -> RowStream:
    return RowStream(
        SpreadsheetRowIR(index=index, values=(index,)) for index in range(count)
    )


def _table_ir(rows: object) -> SpreadsheetTableIR:
    return SpreadsheetTableIR(
        name="sales",
        anchor=CellAddress(1, 1),
        columns=(),
        rows=rows,  # type: ignore[arg-type]
    )


def test_row_stream_reports_a_second_pass_instead_of_yielding_nothing() -> None:
    stream = _row_stream(2)

    assert len(tuple(stream.consume())) == 2

    with pytest.raises(InvalidOperationError, match="one-shot"):
        tuple(stream.consume())


def test_table_ir_wraps_a_bare_iterable_in_a_row_stream() -> None:
    table_ir = _table_ir(iter((SpreadsheetRowIR(index=0, values=(1,)),)))

    assert isinstance(table_ir.rows, RowStream)
    assert table_ir.rows.row_count is None
    assert len(tuple(table_ir.rows)) == 1


def test_materialized_row_stream_can_be_read_again() -> None:
    materialized = _row_stream(3).materialized()

    assert materialized.row_count == 3
    assert len(tuple(materialized)) == 3
    assert len(tuple(materialized.materialized())) == 3


def test_resolved_formula_base_is_abstract_and_the_union_is_closed() -> None:
    with pytest.raises(CaxtonTypeError, match="abstract"):
        ResolvedFormula()

    assert len(ResolvedFormulaNode.__args__) == 4
    assert all(
        issubclass(node, ResolvedFormula) for node in ResolvedFormulaNode.__args__
    )


def test_user_semantic_type_renders_through_its_declared_format() -> None:
    document = spreadsheet(
        sheet(
            "Ratings",
            table(
                source=({"score": 4.5},),
                columns=(make_column("score", Rating(), "score"),),
            ),
        ),
    )

    result = render(document)

    assert result.bytes_written > 0


def test_numeric_flag_selects_total_columns() -> None:
    numeric = Column(
        id="score",
        semantic_type=Rating(),
        source=make_column("score", Rating(), "score").source,
    )

    assert numeric.semantic_type.numeric is True
    assert text(source="name", id="name").semantic_type.numeric is False


def test_template_target_rejects_a_column_reference() -> None:
    assert isinstance(slot("items"), TemplateRef)
    assert repeat("items").reference == slot("items")

    with pytest.raises(CaxtonTypeError, match="slot"):
        table(
            source=_ROWS,
            columns=(integer(source="amount"),),
            into=col("amount"),  # type: ignore[arg-type]
        )


def test_width_and_auto_width_conflict_is_reported() -> None:
    declared = integer(source="amount", id="amount")

    assert declared.width(10).auto_width is None
    assert declared.width("auto").width_hint is None

    with pytest.raises(CaxtonValueError, match="both an explicit width"):
        dataclasses.replace(declared, width_hint=10, auto_width=True)


def test_currency_that_a_format_cannot_show_is_reported() -> None:
    kept = money(source="amount", currency="EUR").format(money_format(places=0))

    assert isinstance(kept.semantic_type, Money)
    assert kept.semantic_type.currency == "EUR"

    with pytest.raises(CaxtonValueError, match="cannot display"):
        money(source="amount", currency="EUR").format(decimal_format())


def test_money_carries_its_currency_into_the_default_format() -> None:
    assert money(source="amount", currency="USD").semantic_type.default_format() == (
        money_format(currency="USD", places=2, grouping=True)
    )
    assert decimal(source="amount").semantic_type.default_format() is None


def test_public_accessor_completes_a_third_party_data_source() -> None:
    document = spreadsheet(
        sheet(
            "Data",
            table(
                source=_CursorSource(({"amount": 7},)),
                columns=(integer(source="amount"),),
            ),
        ),
    )

    assert render(document).bytes_written > 0


def test_public_xlsx_surface_does_not_reexport_internals() -> None:
    assert not xlsx.pivot.__module__.startswith("caxton._internal")
    assert not xlsx.PivotBinding.__module__.startswith("caxton._internal")


def test_unreadable_image_names_its_source() -> None:
    document = spreadsheet(
        sheet("Cover", image(source="/nonexistent/logo.png", name="logo")),
    )

    with pytest.raises(RenderError) as captured:
        render(document)

    assert captured.value.context["source"] == "/nonexistent/logo.png"


def test_relative_axis_flags_are_deprecated() -> None:
    made_relative = col("price").absolute().relative()

    assert made_relative.column_absolute is False
    assert made_relative.row_absolute is False

    with pytest.deprecated_call():
        col("price").relative(row=False)


def test_error_context_is_visible_when_printed() -> None:
    document = spreadsheet(
        sheet("Data", table(source=_ROWS, columns=(integer(source="missing"),))),
    )

    with pytest.raises(MissingFieldError) as captured:
        render(document)

    assert "Context:" in str(captured.value)
    assert "field: 'missing'" in str(captured.value)


def test_notification_raises_the_requested_validation_error() -> None:
    notification = Notification()
    notification.add("Row count does not match", path="sheet[0]")

    with pytest.raises(ShapeError):
        notification.raise_if_errors(error_class=ShapeError)

    with pytest.raises(CaxtonTypeError, match="ValidationError type"):
        notification.raise_if_errors(error_class=RenderResult)  # type: ignore[arg-type]
