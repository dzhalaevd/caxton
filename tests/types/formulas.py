from typing import assert_type

from caxton import absolute, col, decimal, sheet_ref, table_ref
from caxton.core.models import (
    CellReference,
    Column,
    FormulaBinary,
    RangeReference,
)

current_cell = col("price")
formula = current_cell - col("base_price").absolute(row=False)
named_range = table_ref("sales").column("price")
cross_sheet_cell = sheet_ref("Sales").table("sales").column("price").cell(0)
formula_column = decimal(id="delta", formula=formula)

assert_type(current_cell, CellReference)
assert_type(formula, FormulaBinary)
assert_type(named_range, RangeReference)
assert_type(cross_sheet_cell, CellReference)
assert_type(absolute(current_cell), CellReference)
assert_type(absolute(named_range), RangeReference)
assert_type(formula_column, Column)
