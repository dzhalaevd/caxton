# Grouping and aggregation

## Aggregate expressions

Any row expression can be aggregated with `.agg()`. The function is an arbitrary
Python callable — Caxton passes it one value sequence per input expression and
does not normalize inputs or drop `None`.

```python
from caxton import decimal, field

decimal(id="active_oil", source=field("oil_rate").agg(sum))
```

| Argument       | Meaning                                                           |
|----------------|-------------------------------------------------------------------|
| `function`     | Callable receiving one sequence per input expression.             |
| `*expressions` | Additional inputs, aggregated over the same scope.                |
| `where`        | Non-aggregate filter expression applied before the callable runs. |
| `default`      | Result used when filtering leaves the scope empty.                |

```python
field("oil_rate").agg(sum, where=field("active"), default=0)
```

When a filter empties a scope:

- with an explicit `default`, that value is returned and the callable is never called;
- without one, the callable keeps authority over the empty input, and any failure
  is reported as `AggregateEvaluationError`.

An ungrouped table treats the whole source as one scope. A grouped table uses
one leaf group per scope.

## Grouped tables

Grouping is column intent, not a separate table type. Declare it with
`.grouped()`; the hierarchy follows the physical declaration order of the
grouped columns.

```python
from caxton import decimal, field, table, text

table(
    source=production,
    columns=(
        text(source="shop", title="Shop").grouped(merge=True),
        text(source="field", title="Field").grouped(),
        decimal(
            id="active_oil",
            source=field("oil_rate").agg(sum, where=field("active"), default=0),
            title="Active oil",
        ),
    ),
)
```

| Option  | Values                                        | Effect                                     |
|---------|-----------------------------------------------|--------------------------------------------|
| `merge` | `True` / `False`                              | Merges repeated cells of that group level. |
| `order` | `"first_seen"`, `"ascending"`, `"descending"` | Ordering policy for that level.            |

Ordering notes:

- `first_seen` (the default) keeps the order the source produced.
- Sorted levels place `None` **last** in both ascending and descending order.

## Dimension identity

Group keys use strict Python identity. `True`, `1`, `Decimal("1")` and
`Decimal("1.0")` form four separate groups. Float `-0.0` folds into `0.0`, and
all NaN values collapse into one canonical group.

## Matrices

A `Matrix` is a pivot-like block with typed row-dimension, column-dimension and
value columns. Axis keys are discovered from the data.

```python
from caxton import decimal, field, matrix

matrix(
    source=production,
    row=field("shop"),
    column=field("month"),
    value=decimal(id="oil_total", source=field("oil_rate").agg(sum)),
)
```

- `row` and `column` accept a single column or expression, or a sequence for a
  multi-level axis. Bare expressions are normalized into columns.
- `value` must resolve every cell to exactly one value; when more than one source
  value lands in a cell, an `AggregateExpr` is required or `MatrixConflictError`
  is raised.
- Dynamic keys appear in first-seen order unless the dimension column declares a
  grouping `order`.
- Row-dimension merge intent produces vertical merges. Flattened column headers
  reject merge intent.

Generated value columns expose their dimension key through the testing layout,
so assertions do not have to depend on compiler-generated ids.

## Data consumption

Grouped tables and matrices need the complete source to know their output shape,
so they buffer semantic input rows internally and consume a `ONE_SHOT` source
**exactly once**. Aggregate inputs are evaluated during that pass, after their
filters, so the original row object can be released early. Matrix output rows are
emitted lazily once the dynamic axes are known, so a sparse input does not also
retain a dense Cartesian output.

This is a documented single pass, not an append-only streaming plan.

!!! warning

    Because structural validation never reads rows, a clean `validate()` cannot
    guarantee a clean render here. Preparation can consume a one-shot source
    before the second placement check discovers a block overlap; after that
    failure the source stays consumed.
