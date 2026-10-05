# Formulas and computation

A derived value can be finished before the workbook is written, or it can remain a formula that the spreadsheet
recalculates later. That choice is part of the document model. Make it from the behavior you want in the finished file,
not from which syntax happens to be shorter.

| Value origin                              | Evaluated by                  | Written to the workbook as |
|-------------------------------------------|-------------------------------|----------------------------|
| `field()`, `path()`, `ref()`, `literal()` | Caxton                        | A literal value            |
| `.transform()` or a callable source       | Caxton's row evaluator         | A literal value            |
| `.agg()`                                  | Caxton, over a declared scope | A literal value            |
| `col()`, `table_ref()`, `sheet_ref()`     | The spreadsheet               | A live formula             |
| A `Total` in a table footer               | The spreadsheet               | A live aggregate formula   |

The two expression families are deliberately separate. A Python expression may read source data and other evaluated
semantic values. Application code owns transform and callable functions, but Caxton invokes them while evaluating rows.
A spreadsheet formula refers to cells and ranges that will exist after layout.

## Compute row values before rendering

Use a Python row expression when the result belongs to your application logic and should be fixed in the generated
artifact. The expression keeps its inputs visible to validation and testing:

```python
from decimal import Decimal

from caxton import field, integer, literal, money, path, percentage, ref, text

books = (
    {
        "title": "Kindred",
        "list_price": Decimal("16.00"),
        "discount": Decimal("0.15"),
        "stock": {"copies": 4},
    },
    {
        "title": "Piranesi",
        "list_price": Decimal("14.00"),
        "discount": Decimal("0"),
        "stock": {"copies": 0},
    },
)

book_columns = (
    text(source="title", title="Title"),
    money(source="list_price", title="List price", currency="USD"),
    percentage(source="discount", title="Discount"),
    integer(id="copies", source=path("stock", "copies"), title="Copies"),
    money(
        id="sale_price",
        source=ref("list_price") * (1 - ref("discount")),
        title="Sale price",
        currency="USD",
    ),
    text(id="edition", source=literal("Print"), title="Edition"),
)
```

Each reference has one job:

- `field("list_price")` reads an exact top-level field from the source row. A string passed as `source=` is shorthand
  for the same operation.
- `path("stock", "copies")` traverses nested mappings or objects explicitly. Dots inside a string have no path meaning.
- `ref("list_price")` reads the evaluated value of another semantic column in the same table.
- `literal("Print")` supplies the same scalar value for every row.

`ref()` resolves semantic ids, so changing a column title or moving the column does not break the calculation.
Referenced columns may appear later in the display order. Caxton builds the dependency graph separately and rejects
missing ids or cycles during structural validation, without reading a row.

Python expressions support arithmetic, comparisons, and boolean composition with `&` and `|`. Parenthesize comparisons
when you combine them:

```python
eligible = (field("discount") > 0) & (path("stock", "copies") > 0)
```

## Keep ordinary Python logic in Python

Arithmetic composes naturally as expressions. A lookup or a branch is usually clearer as an application function.
`.transform()` applies one function to the value produced by an expression while retaining that input as a visible
dependency:

```python
from collections.abc import Mapping


def availability(copies: object) -> str:
    return "In stock" if copies else "Out of stock"


stock_label = text(
    id="availability",
    source=path("stock", "copies").transform(availability),
    title="Availability",
)

shelf_by_genre: Mapping[str, str] = {
    "fiction": "Main room",
    "essay": "Reading room",
}

shelf = text(
    id="shelf",
    source=field("genre").transform(shelf_by_genre.__getitem__),
    title="Shelf",
)
```

When a calculation needs the complete source object, pass a named callable as the column source. That boundary is useful
for multi-field rules that would become hard to read as chained operators. Caxton calls it with the original row; unlike
an expression tree, the callable's internal dependencies are application-owned and are not available to structural
inspection.

Caxton does not provide raw formula strings or formula nodes for `IF`, `VLOOKUP`, `XLOOKUP`, or `INDEX`/`MATCH`. Put
conditional and lookup rules in the Python row layer. The generated workbook then contains their results rather than
opaque formula text that Caxton cannot validate.

## Leave a calculation live in the workbook

Use a spreadsheet formula when readers should be able to edit an input cell and see the result recalculate. `col()`
refers to another semantic column in the current data row:

```python
from caxton import col

live_columns = (
    text(source="title", title="Title"),
    money(source="list_price", title="List price", currency="USD"),
    percentage(source="discount", title="Discount"),
    money(
        id="sale_price",
        formula=col("list_price") * (1 - col("discount")),
        title="Sale price",
        currency="USD",
    ),
)
```

The compiler resolves `list_price` and `discount` after layout, then the XLSX renderer writes the corresponding cell
formula. Column ids remain stable even if the table moves to another anchor.

A column has exactly one value origin. Pass either `source=` or `formula=`. The generative `.formula()` method is useful
when adapting an existing declaration; it returns a new column whose Python source has been replaced by formula intent.

Caxton writes formulas but does not calculate them. Semantic and layout inspection can show the resolved formula, while
the final value appears after a spreadsheet application recalculates the workbook.

## Refer to another row, table, or worksheet

Formula references start from semantic names rather than A1 coordinates:

```python
from caxton import sheet_ref, table_ref

price_range = table_ref("books").column("sale_price")
first_price = price_range.cell(0)
first_price_on_catalog = (
    sheet_ref("Catalog").table("books").column("sale_price").cell(0).absolute()
)
```

`table_ref("books")` requires a table declared with `name="books"`. `.column("sale_price")` selects its data range, and
`.cell(0)` narrows the range to its first data row; row indexes are zero-based. Add `sheet_ref()` when the reference
must name a particular worksheet.

A full range needs a known row count because the compiler must resolve both ends before rendering. Caxton will not make
a hidden pass over a generator or another unknown-length source to discover that boundary. A list, tuple, or a custom
data source that reports `row_count` can be used for range references.

## Control copied references

References are relative by default. Use `.absolute()` when one or both axes must remain fixed as a formula is copied:

| Declaration                                | Column axis | Row axis |
|--------------------------------------------|-------------|----------|
| `col("list_price")`                        | Relative    | Relative |
| `col("list_price").absolute(row=False)`    | Absolute    | Relative |
| `col("list_price").absolute(column=False)` | Relative    | Absolute |
| `col("list_price").absolute()`             | Absolute    | Absolute |

The free `absolute(reference, ...)` function applies the same rule to a cell or range reference. Prefer it, or the
method above, when fixing one axis; the per-axis form of `relative()` is deprecated because its flags are inverted.

## Use formulas for conditional presentation

Conditional formatting evaluates in the finished spreadsheet, so its condition uses the formula family too:

```python
from caxton import Style, sheet, spreadsheet, table, when

catalog = spreadsheet(
    sheet(
        "Catalog",
        table(
            source=books,
            columns=live_columns,
            name="books",
            rules=(when(col("discount") > 0, style="discounted"),),
        ),
    ),
    styles={
        "discounted": Style(fill="#FFF2CC"),
    },
)
```

The condition follows the column id if the table moves or the visible title changes. The rule remains live in the XLSX
file; the spreadsheet applies the named style to matching data rows. See
[Values and presentation](presentation.md) for style resolution and themes.

## Know where aggregation happens

Caxton supports two kinds of aggregate, with different results in the artifact.

An aggregate expression runs in Python. In an ordinary ungrouped table, its scope is the complete source and the table
produces one output row:

```python
total_copies = table(
    source=books,
    columns=(
        integer(
            id="copies",
            source=path("stock", "copies").agg(sum),
            title="Copies",
        ),
    ),
)
```

`.agg()` may take additional input expressions, a `where=` filter, and a `default=` for an empty filtered scope. Caxton
passes complete value sequences to the callable; it does not discard `None`.

The surrounding block determines the scope:

| Block | Aggregate scope | Output shape |
|-------|-----------------|--------------|
| Ordinary table without grouping | The complete source. | One output row. |
| Grouped table | One leaf group, defined by all grouped columns. | One row per leaf group. |
| Matrix | One coordinate defined by row and column axis values. | One value cell per axis-key combination. |

The `where=` expression filters only the current scope. `default=` supplies a value when that filter leaves it empty. In
a matrix, a plain non-aggregate value is valid only when at most one source row reaches each coordinate; duplicates raise
`MatrixConflictError`.

An aggregate must be the complete Python source of its column. It cannot be nested inside arithmetic or another
expression. When a later value depends on the aggregate, put the aggregate in one column and refer to that column from a
spreadsheet formula.

A table footer takes the other route:

```python
from caxton import Total, Totals

catalog_table = table(
    source=books,
    columns=live_columns,
    name="books",
    footer=Totals(items=(Total("sale_price"),)),
)
```

`Total("sale_price")` becomes a spreadsheet aggregate over the rendered table range, so it recalculates with the file.
An `AggregateExpr` becomes a literal. See [Tables and data](tables.md#group-rows-when-one-output-row-represents-a-group)
for grouped-table and matrix declarations.

## Validate dependencies before consuming data

`validate()` checks formula and Python-expression references as one structural graph. It reports missing columns,
missing tables or worksheets, and direct or indirect cycles before rendering starts. This remains lazy: validation does
not consume the table source.

One dependency direction is impossible by design. A Python `ref()` expression cannot read a formula-backed column,
because that value does not exist until the spreadsheet calculates it. Keep the dependent value as another formula, or
move both calculations into Python.

For the complete public types, see
[`caxton.core.models`](../reference/models.md) and
[`caxton.api`](../reference/api.md).
