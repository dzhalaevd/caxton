from typing import assert_type

from caxton import AggregateExpr, Grouping, Matrix, decimal, field, matrix, text

aggregate = field("value").agg(sum, default=0)
grouped = text("key").grouped(merge=True)
pivot = matrix(
    [],
    row=text("shop"),
    column=text("month"),
    value=decimal("total", source=aggregate),
)

assert_type(aggregate, AggregateExpr)
assert_type(grouped.grouping, Grouping | None)
assert_type(pivot, Matrix)
