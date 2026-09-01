from collections.abc import Iterator, Sequence
from decimal import Decimal
from typing import Any

import pytest

from caxton import (
    AggregateEvaluationError,
    AggregateExpr,
    DataSourceConsumedError,
    FieldRef,
    GroupingError,
    GroupOrder,
    Matrix,
    MatrixConflictError,
    UnsupportedFeatureError,
    ValidationError,
    col,
    decimal,
    decimal_format,
    field,
    matrix,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    title,
    validate,
)
from caxton.testing import (
    Rows,
    SourceKind,
    inspect_artifact,
    inspect_layout,
    inspect_spec,
)


def test_aggregate_expr_contract() -> None:
    def weighted_average(
        prices: Sequence[int],
        quantities: Sequence[int],
    ) -> object:
        return sum(
            price * quantity for price, quantity in zip(prices, quantities, strict=True)
        ) / sum(quantities)

    condition = field("active") == True  # noqa: E712
    expression = field("price").agg(
        weighted_average,
        field("quantity"),
        where=condition,
    )

    assert isinstance(expression, AggregateExpr)
    assert expression.function is weighted_average
    assert [
        item.name for item in expression.expressions if isinstance(item, FieldRef)
    ] == ["price", "quantity"]
    assert expression.where is condition


def test_grouping_and_matrix_semantics() -> None:  # noqa: WPS218
    shop = text(id="shop", source="shop").grouped(merge=True, order="ascending")
    value = field("oil_rate").agg(sum)
    report = matrix(
        source=[],
        row=field("shop"),
        column=field("month"),
        value=value,
    )

    assert shop.grouping is not None
    assert shop.grouping.merge is True
    assert shop.grouping.order is GroupOrder.ASCENDING
    assert isinstance(report, Matrix)
    assert isinstance(report.row_dimensions[0].source, FieldRef)
    assert report.row_dimensions[0].source.name == "shop"
    assert isinstance(report.column_dimensions[0].source, FieldRef)
    assert report.column_dimensions[0].source.name == "month"
    assert report.value.source is value
    assert decimal(id="total", source=value).source is value

    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[],
                columns=(
                    shop,
                    decimal(id="total", source=value),
                ),
                name=None,
            ),
            report,
        ),
    )
    inspected = inspect_spec(document)
    semantic_table = inspected.worksheet("Summary").tables[0]
    assert semantic_table.columns[0].grouping == shop.grouping
    aggregate_source = semantic_table.column("total").source
    assert aggregate_source is not None
    assert aggregate_source.kind is SourceKind.AGGREGATE
    matrix_block = inspected.worksheet("Summary").blocks[1]
    assert matrix_block.kind.value == "matrix"
    assert matrix_block.matrix is not None
    assert matrix_block.matrix.value.source is not None
    assert matrix_block.matrix.value.source.kind is SourceKind.AGGREGATE


def test_matrix_strings_normalize_to_fields() -> None:
    report = matrix(
        source=[],
        row=("shop", text(id="field", source="field", title="Field")),
        column="month",
        value=field("oil_rate"),
    )

    shop, field_dimension = report.row_dimensions
    month = report.column_dimensions[0]
    assert isinstance(shop.source, FieldRef)
    assert isinstance(month.source, FieldRef)
    assert (
        shop.id,
        shop.source.name,
        field_dimension.id,
        field_dimension.title,
        month.source.name,
    ) == ("shop", "shop", "field", "Field", "month")


def test_matrix_strings_keep_rows_lazy() -> None:
    visited = False

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visited
        visited = True
        yield {"shop": "A", "month": "Jan", "oil_rate": 1}

    matrix(
        source=rows(),
        row="shop",
        column="month",
        value=field("oil_rate"),
    )

    assert not visited


@pytest.mark.parametrize("row", [1, ("shop", object())])
def test_matrix_rejects_invalid_dimensions(row: Any) -> None:
    with pytest.raises(
        TypeError,
        match="Matrix dimensions must be columns, expressions, or field names",
    ):
        matrix(
            source=[],
            row=row,
            column="month",
            value=field("oil_rate"),
        )


def test_grouped_aggregate_layout() -> None:
    def weighted_average(
        prices: Sequence[int],
        quantities: Sequence[int],
    ) -> object:
        numerator = sum(
            price * quantity for price, quantity in zip(prices, quantities, strict=True)
        )
        return numerator / sum(quantities)

    rows = [
        {"shop": "B", "field": "Z", "price": 3, "quantity": 2, "active": True},
        {"shop": "A", "field": "X", "price": 10, "quantity": 2, "active": True},
        {"shop": "A", "field": "X", "price": 20, "quantity": 1, "active": False},
        {"shop": "A", "field": "Y", "price": 5, "quantity": 4, "active": True},
    ]
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=rows,
                columns=(
                    text(id="shop", source="shop").grouped(
                        merge=True, order="ascending"
                    ),
                    text(id="field", source="field").grouped(order="descending"),
                    decimal(
                        id="weighted_price",
                        source=field("price").agg(
                            weighted_average,
                            field("quantity"),
                            where=field("active"),
                        ),
                    ),
                ),
            ),
        ),
    )

    layout = inspect_layout(document, rows=Rows.all())
    grouped = layout.worksheet("Summary").tables[0]

    assert [row.values for row in grouped.rows] == [
        {"shop": "A", "field": "Y", "weighted_price": 5},
        {"shop": "A", "field": "X", "weighted_price": 10},
        {"shop": "B", "field": "Z", "weighted_price": 3},
    ]
    assert grouped.merged_ranges == ("A2:A3",)


def test_grouped_one_shot_single_pass() -> None:
    visits = 0

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visits
        visits += 1
        yield {"shop": "A", "value": 1}
        yield {"shop": "A", "value": 2}

    semantic_table = table(
        source=rows(),
        columns=(
            text(id="shop", source="shop").grouped(),
            decimal(id="total", source=field("value").agg(sum)),
        ),
    )
    document = spreadsheet(sheet("Summary", semantic_table))

    inspected = inspect_layout(document, rows=Rows.all())

    assert inspected.worksheet("Summary").tables[0].row(0).values["total"] == 3
    assert visits == 1
    with pytest.raises(DataSourceConsumedError):
        semantic_table.data.source.iter_rows()


def test_grouped_stream_diagnostic() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"shop": "A", "value": 1}],
                columns=(
                    text(id="shop", source="shop").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )

    with pytest.raises(UnsupportedFeatureError) as captured:
        render(document, mode="stream")

    assert captured.value.context["reason"] == "shape_dependent_buffering"


def test_grouped_height_places_next_block() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[
                    {"shop": "A", "value": 1},
                    {"shop": "A", "value": 2},
                    {"shop": "B", "value": 3},
                ],
                columns=(
                    text(id="shop", source="shop").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
            title("After groups", anchor="A4"),
        ),
    )

    inspected = inspect_layout(document, rows=Rows.all())

    assert inspected.worksheet("Summary").block("block[1]").anchor == "A4"


def test_empty_ungrouped_scope() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[],
                columns=(decimal(id="total", source=field("value").agg(sum)),),
            ),
        ),
    )

    inspected = inspect_layout(document, rows=Rows.all())

    assert inspected.worksheet("Summary").tables[0].row(0).values == {"total": 0}


def test_empty_grouped_scope_has_headers_only() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[],
                columns=(
                    text(id="shop", source="shop").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )

    inspected = inspect_layout(document, rows=Rows.all())

    assert inspected.worksheet("Summary").tables[0].rows == ()


def test_aggregate_none_and_errors() -> None:  # noqa: WPS218
    received: tuple[object, ...] = ()

    def preserve(values: Sequence[object]) -> object:
        nonlocal received
        received = tuple(values)
        return len(values)

    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"value": None}, {"value": 2}],
                columns=(decimal(id="count", source=field("value").agg(preserve)),),
            ),
        ),
    )

    inspect_layout(document, rows=Rows.all())

    assert received == (None, 2)

    failing = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[],
                columns=(decimal(id="minimum", source=field("value").agg(min)),),
            ),
        ),
    )
    with pytest.raises(AggregateEvaluationError) as captured:
        inspect_layout(failing, rows=Rows.all())

    assert captured.value.context["function"] == "min"
    assert captured.value.context["scope_size"] == 0
    assert captured.value.context["phase"] == "callable"
    assert (
        captured.value.path == 'worksheet["Summary"].block[0].column["minimum"].source'
    )
    assert isinstance(captured.value.__cause__, ValueError)

    unsupported = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"value": 1}],
                columns=(
                    decimal(id="bad", source=field("value").agg(lambda _values: [])),
                ),
            ),
        ),
    )
    with pytest.raises(AggregateEvaluationError) as captured:
        inspect_layout(unsupported, rows=Rows.all())

    assert captured.value.context["phase"] == "result_normalization"


def test_ambiguous_aggregate_scope() -> None:
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

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert {issue.code for issue in captured.value.issues} == {
        "ambiguous_aggregate_scope",
    }


def test_matrix_aggregates_duplicates() -> None:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=[
                    {"shop": "A", "month": "Jan", "oil": 2},
                    {"shop": "A", "month": "Jan", "oil": 3},
                    {"shop": "A", "month": "Feb", "oil": 4},
                    {"shop": "B", "month": "Jan", "oil": 7},
                ],
                row=field("shop"),
                column=field("month"),
                value=field("oil").agg(sum),
            ),
        ),
    )

    inspected = inspect_layout(document, rows=Rows.all())
    pivot = inspected.worksheet("Matrix").tables[0]

    assert [column.title for column in pivot.columns] == ["shop", "Jan", "Feb"]
    january = pivot.matrix_column("Jan")
    february = pivot.matrix_column("Feb")
    assert pivot.row(0).values[january.id] == 5
    assert pivot.row(0).values[february.id] == 4
    assert pivot.row(1).values[january.id] == 7
    assert pivot.row(1).values[february.id] is None


def test_group_keys_preserve_type_and_scale() -> None:
    keys = (True, 1, Decimal(1), Decimal("1.0"))
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"key": key, "value": 1} for key in keys],
                columns=(
                    text(id="key", source="key").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )

    grouped = inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]

    assert [row.values["key"] for row in grouped.rows] == list(keys)
    assert [row.values["total"] for row in grouped.rows] == [1, 1, 1, 1]


def test_signed_float_zero_uses_one_group() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[  # noqa: WPS358
                    {"key": key, "value": 1}
                    for key in (0.0, -0.0)  # noqa: WPS358
                ],
                columns=(
                    text(id="key", source="key").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )

    grouped = inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]

    assert len(grouped.rows) == 1
    assert grouped.row(0).values["total"] == 2


def test_float_nan_uses_one_canonical_group() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"key": float("nan"), "value": 1} for _index in range(2)],
                columns=(
                    text(id="key", source="key").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )

    grouped = inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]

    assert len(grouped.rows) == 1
    assert grouped.row(0).values["total"] == 2


def test_matrix_ids_do_not_collide() -> None:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=[{"value_0": "A", "month": "Jan", "oil": 2}],
                row=(field("value_0"), field("value_0")),
                column=field("month"),
                value=field("oil").agg(sum),
            ),
        ),
    )

    pivot = inspect_layout(document, rows=Rows.all()).worksheet("Matrix").tables[0]

    assert len(pivot.column_ids) == len(set(pivot.column_ids))
    assert pivot.row(0).values["value_0"] == "A"
    assert pivot.row(0).values["value_0_2"] == "A"
    assert pivot.row(0).values[pivot.matrix_column("Jan").id] == 2


def test_matrix_value_preserves_formatting() -> None:
    value = (
        decimal(id="oil", source=field("oil").agg(sum))
        .format(decimal_format(places=2))
        .width(14)
    )
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=[{"shop": "A", "month": "Jan", "oil": Decimal("2.5")}],
                row=field("shop"),
                column=field("month"),
                value=value,
            ),
        ),
    )

    pivot = inspect_layout(document, rows=Rows.all()).worksheet("Matrix").tables[0]
    january = pivot.matrix_column("Jan")

    assert january.semantic_type.name == "decimal"
    assert january.width == 14
    assert january.display_format == decimal_format(places=2)


def test_overlap_before_matrix_consumption() -> None:
    visits = 0

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visits
        visits += 1
        yield {"shop": "A", "month": "Jan", "oil": 1}

    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=rows(),
                row=field("shop"),
                column=field("month"),
                value=field("oil").agg(sum),
                anchor="E10",
            ),
            title("First", anchor="A1"),
            title("Second", anchor="A1"),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert "block_overlap" in {issue.code for issue in captured.value.issues}
    assert visits == 0


def test_nested_aggregate_is_rejected() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"value": 1}],
                columns=(decimal(id="total", source=field("value").agg(sum) * 2),),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert {issue.code for issue in captured.value.issues} == {
        "nested_aggregate_expression",
    }


def test_formula_in_aggregate_table() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"shop": "A", "value": 2}],
                columns=(
                    text(id="shop", source="shop").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                    decimal(id="double", source="double").formula(col("total") * 2),
                ),
            ),
        ),
    )

    grouped = inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]

    assert grouped.row(0).values["double"] is None
    assert grouped.column("double").formula is not None


def test_aggregate_default_for_empty_filter() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"shop": "A", "value": 2, "active": False}],
                columns=(
                    text(id="shop", source="shop").grouped(),
                    decimal(
                        id="minimum",
                        source=field("value").agg(
                            min,
                            where=field("active"),
                            default=None,
                        ),
                    ),
                ),
            ),
        ),
    )

    grouped = inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]

    assert grouped.row(0).values["minimum"] is None


def test_null_group_is_always_last() -> None:
    for order in ("ascending", "descending"):
        document = spreadsheet(
            sheet(
                "Summary",
                table(
                    source=[{"key": None}, {"key": "A"}, {"key": "B"}],
                    columns=(text(id="key", source="key").grouped(order=order),),
                ),
            ),
        )
        grouped = (
            inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]
        )
        assert grouped.rows[-1].values["key"] is None


def test_matrix_duplicate_conflict() -> None:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=[
                    {"shop": "A", "month": "Jan", "oil": 2},
                    {"shop": "A", "month": "Jan", "oil": 3},
                ],
                row=field("shop"),
                column=field("month"),
                value=field("oil"),
            ),
        ),
    )

    with pytest.raises(MatrixConflictError) as captured:
        inspect_layout(document, rows=Rows.all())

    assert captured.value.context["row_key"] == ("A",)
    assert captured.value.context["column_key"] == ("Jan",)
    assert captured.value.path == 'worksheet["Matrix"].block[0].value["value"]'


def test_grouping_error_has_block_context() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"key": "A"}, {"key": 1}],
                columns=(text(id="key", source="key").grouped(order="ascending"),),
            ),
        ),
    )

    with pytest.raises(GroupingError) as captured:
        inspect_layout(document, rows=Rows.all())

    assert captured.value.path == (
        'worksheet["Summary"].block[0].column["key"].grouping'
    )


def test_matrix_consumes_one_shot_once() -> None:
    visits = 0

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visits
        visits += 1
        yield {"shop": "A", "month": "Jan", "oil": 2}

    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=rows(),
                row=field("shop"),
                column=field("month"),
                value=field("oil").agg(sum),
            ),
        ),
    )

    inspect_layout(document, rows=Rows.all())

    assert visits == 1


def test_matrix_headers_are_nonempty_and_unique() -> None:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=[
                    {"shop": "A", "month": None, "oil": 1},
                    {"shop": "A", "month": 1, "oil": 2},
                    {"shop": "A", "month": Decimal(1), "oil": 3},
                ],
                row=field("shop"),
                column=field("month"),
                value=field("oil").agg(sum),
            ),
        ),
    )

    pivot = inspect_layout(document, rows=Rows.all()).worksheet("Matrix").tables[0]
    headers = [column.title for column in pivot.columns[1:]]

    assert headers[0] == "(blank)"
    assert len(headers) == len(set(headers))
    assert pivot.row(0).values[pivot.matrix_column(1).id] == 2
    assert pivot.row(0).values[pivot.matrix_column(Decimal(1)).id] == 3


def test_merged_groups_reject_autofilter() -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[{"shop": "A"}],
                columns=(text(id="shop", source="shop").grouped(merge=True),),
                autofilter=True,
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert {issue.code for issue in captured.value.issues} == {
        "merged_group_autofilter",
    }


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_group_merges_in_xlsx(
    backend: str,
) -> None:
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=[
                    {"shop": "A", "field": "X", "value": 1},
                    {"shop": "A", "field": "Y", "value": 2},
                    {"shop": None, "field": "Z", "value": 3},
                ],
                columns=(
                    text(id="shop", source="shop").grouped(merge=True),
                    text(id="field", source="field").grouped(),
                    decimal(id="total", source=field("value").agg(sum)),
                ),
            ),
        ),
    )

    artifact = inspect_artifact(render(document, backend=backend))
    worksheet = artifact.worksheet("Summary")

    assert worksheet.merged_ranges == ("A2:A3",)
    assert worksheet.cell("A2").value == "A"
    assert worksheet.cell("B4").value == "Z"
    assert worksheet.cell("C2").value == 1


def test_matrix_xlsx_grid() -> None:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=[
                    {"shop": "A", "month": "Jan", "oil": 2},
                    {"shop": "A", "month": "Jan", "oil": 3},
                    {"shop": "B", "month": "Feb", "oil": 4},
                ],
                row=field("shop"),
                column=field("month"),
                value=field("oil").agg(sum),
            ),
        ),
    )

    worksheet = inspect_artifact(render(document)).worksheet("Matrix")

    assert worksheet.cell("A1").value == "shop"
    assert worksheet.cell("B1").value == "Jan"
    assert worksheet.cell("C1").value == "Feb"
    assert worksheet.cell("B2").value == 5
    assert worksheet.cell("C3").value == 4
