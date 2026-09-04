# Values and display formats

## Semantic types

A column's semantic type describes *what the value means*, not how a backend
stores it. The renderer chooses the physical representation and emits a
capability diagnostic when it cannot preserve the semantics.

| Type         | Meaning                                        |
|--------------|------------------------------------------------|
| `Text`       | Free-form string.                              |
| `Integer`    | Whole number.                                  |
| `Decimal`    | Exact fractional number.                       |
| `Money`      | Amount with an optional currency.              |
| `Percentage` | Ratio displayed as a percentage.               |
| `Boolean`    | True/false.                                    |
| `Date`       | Calendar date.                                 |
| `Time`       | Time of day.                                   |
| `DateTime`   | Date and time.                                 |
| `Duration`   | Elapsed time.                                  |
| `Link`       | Hyperlink target.                              |

You rarely construct these directly — the column factories in
[`caxton.api`](../reference/api.md) do it for you. They live in
[`caxton.core.types`](../reference/types.md) for custom renderers.

Currency belongs to the value: `money(currency="EUR")` states it once, and the
column renders with it even when no display format is given. `money_format(
currency=...)` overrides that for presentation; a format that cannot show a
currency at all — `decimal_format()`, say — is rejected when the column declares
one, instead of dropping it silently.

The set is open. A semantic type of your own declares how it behaves rather
than waiting to be recognized by name:

```python
from typing import ClassVar

from caxton.core.formatting import CustomFormat
from caxton.core.types import SemanticType


class Rating(SemanticType):
    name: ClassVar[str] = "rating"
    numeric: ClassVar[bool] = True  # a totals row may aggregate it

    def default_format(self) -> CustomFormat:
        return CustomFormat(name="rating", pattern="0.0")
```

Any renderer reporting the `semantic:extension` capability — both bundled XLSX
backends do — renders it through that declared format, so no renderer change is
needed to introduce one.

`Decimal` scale is preserved: `Decimal("1")` and `Decimal("1.0")` are distinct
values, which matters when they become grouping or matrix dimension keys.

## Display formats

Formatting is stored separately from value semantics, so the same `Money` column
can be displayed with or without grouping without changing what it means.

```python
from caxton.core.formatting import (
    custom_format,
    date_format,
    decimal_format,
    money_format,
    percentage_format,
    time_format,
)

decimal_format(places=2, grouping=True)
money_format(currency="USD", places=2, grouping=True)
percentage_format(places=1)
date_format(variant="iso")       # "iso" | "short" | "long"
time_format(seconds=False, clock=12)
custom_format("accounting", "#,##0.00_);[Red](#,##0.00)")
```

`custom_format(name, pattern)` is the escape hatch: a named semantic format with
an XLSX-compatible fallback pattern for backends that understand it.

Attach a format to a column or fold it into a reusable style:

```python
from caxton import Style, decimal

decimal(source="amount").format(decimal_format(grouping=True))

Style(display_format=decimal_format(grouping=True))
```

## Value normalization

Values are normalized once, at the semantic boundary, so identity is predictable:

- Python value types stay distinct — `True`, `1` and `Decimal("1")` are three
  different values, not one.
- Float identity folds `-0.0` into `0.0`, and every NaN into one canonical value.
- Non-finite numeric literals are rejected in formulas.

This matters most for [grouping and matrices](grouping-and-aggregation.md),
where values become dimension keys.
