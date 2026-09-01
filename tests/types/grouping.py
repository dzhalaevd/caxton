from typing_extensions import assert_type

from caxton import AggregateExpr, Column, Grouping, Matrix, decimal, field, matrix, text

aggregate = field("value").agg(sum, default=0)
grouped = text(id="key", source="key").grouped(merge=True)
titled = text(id="key", source="key", title="Key")
pivot = matrix(
    source=[],
    row=("shop", text(id="field", source="field", title="Field")),
    column="month",
    value=decimal(id="total", source=aggregate),
)
invalid_axis = matrix(
    source=[],
    row=1,  # type: ignore[arg-type]
    column="month",
    value=decimal(id="total", source=aggregate),
)

assert_type(aggregate, AggregateExpr)
assert_type(grouped.grouping, Grouping | None)
assert_type(titled, Column)
assert_type(pivot, Matrix)
