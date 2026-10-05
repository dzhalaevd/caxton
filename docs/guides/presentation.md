# Values and presentation

A cell that contains `0.75` could mean a quantity, a ratio or part of a monetary amount. Caxton keeps that meaning
separate from its appearance. A column declares the semantic value first; a display format controls how that value is
printed; styles and themes control the surrounding cell.

That separation lets you change the workbook's appearance without changing its schema or row logic.

## Give each value a meaning

The column factories attach a built-in semantic type to each value:

| Value family | Semantic types                         | Typical Python values                                 |
|--------------|----------------------------------------|-------------------------------------------------------|
| Text         | `Text`, `Link`                         | `str`                                                 |
| Numbers      | `Integer`, `Decimal`                   | `int`, `float`, `decimal.Decimal`                     |
| Quantities   | `Money`, `Percentage`                  | Numeric values; percentages are ratios such as `0.75` |
| Time         | `Date`, `Time`, `DateTime`, `Duration` | Values from `datetime`                                |
| Logical      | `Boolean`                              | `bool`                                                |

Here the raw values happen to be numbers and dates, but the columns preserve what those values mean:

```python
import datetime as dt
from decimal import Decimal

from caxton import date, money, percentage, text

books = (
    {
        "title": "Kindred",
        "published": dt.date(1979, 6, 1),
        "price": Decimal("14.50"),
        "progress": Decimal("1.0"),
    },
    {
        "title": "Piranesi",
        "published": dt.date(2020, 9, 15),
        "price": Decimal("12.00"),
        "progress": Decimal("0.35"),
    },
)

book_columns = (
    text(source="title", title="Title"),
    date(source="published", title="Published"),
    money(source="price", title="Price", currency="USD"),
    percentage(source="progress", title="Read"),
)
```

`Money(currency="USD")` carries its currency even when no explicit display format is present. `Percentage` records that
the source is a ratio: `0.35` means 35 percent. The renderer receives those semantics and chooses an appropriate
physical representation for the output format.

Semantic types also drive other behavior. The `numeric` flag controls which columns `Totals()` selects automatically
when no explicit items are supplied. Grouping and matrix dimensions retain the identity of their Python values: `True`,
`1` and `Decimal("1")` do not collapse into the same key.

## Choose how a value is displayed

A display format changes the visible representation, not the value or its semantic type. Attach one with the generative
`.format()` method:

```python
from caxton import date_format, money_format, percentage_format

formatted_columns = (
    text(source="title", title="Title"),
    date(source="published", title="Published").format(
        date_format(variant="long"),
    ),
    money(source="price", title="Price", currency="USD").format(
        money_format(places=0, grouping=True),
    ),
    percentage(source="progress", title="Read").format(
        percentage_format(places=0),
    ),
)
```

The original columns remain unchanged; each call returns a new immutable column. The standard formats cover decimal,
money, percentage, date and time values. Use `custom_format()` when the standard vocabulary cannot express a required
representation:

```python
from caxton import custom_format, integer

page_count = integer(source="pages", title="Length").format(
    custom_format("page-count", '#,##0 "pages"'),
)
```

A custom format has a semantic name and an XLSX-compatible fallback pattern. Keep the semantic type honest: a custom
pattern should change only the display. It should not turn an integer column into a date or give a unitless decimal the
meaning of money.

Currency is a stricter case. It belongs to `Money`, so Caxton rejects a format that would silently discard a declared
currency. `money_format(currency="EUR")` may deliberately override the displayed currency; `decimal_format()` may not.

## Compose cell styles

`Style` collects backend-neutral presentation such as fonts, fills, borders, alignment and display formats. It accepts
structured values where they matter and short forms for common cases:

```python
from caxton import CellAlignment, FontStyle, Style

heading = Style(
    font=FontStyle(name="Arial", size=16, bold=True, color="#24324A"),
    fill="#E8EDF5",
    border_bottom="thin",
)

wrapped_text = Style(
    alignment=CellAlignment(vertical="top", wrap_text=True),
)

centered = Style(align="center")
```

Colors use `#RRGGBB` notation. Border shorthands accept `thin`, `medium`, `thick`, `dashed`, `dotted` and `double`. Use
`BorderLine` when one side also needs its own color.

An inline style is useful for a single declaration. Give repeated styles names at the document boundary:

```python
from caxton import DocumentTheme

library_theme = DocumentTheme(
    default=Style(font=FontStyle(name="Arial", size=10)),
    header=Style(
        font=FontStyle(bold=True, color="#FFFFFF"),
        fill="#405A7A",
    ),
    total=Style(font=FontStyle(bold=True), border_top="double"),
)

library_styles = {
    "section-title": heading,
    "body": Style(border_bottom="thin"),
    "currency": Style(
        align="right",
        display_format=money_format(places=2, grouping=True),
    ),
    "finished": Style(fill="#DDEEDD", font_color="#245B35"),
}
```

Passing the mapping as `styles=` to `spreadsheet()` normalizes it into an immutable `StyleSheet`. Blocks and columns can
then refer to a name instead of copying the value. Keep these names role-based: `currency`, `section-title` and
`finished` say what the style is for without tying it to a cell coordinate or renderer.

## Apply defaults at the right scope

A theme supplies workbook-wide defaults. Named styles describe reusable roles within that workbook. Inline styles are
best reserved for a genuine one-off.

Caxton merges styles component by component, so a column that changes only its display format still inherits the
document font and the table border. The effective order depends on the kind of cell:

| Cells        | Resolution order, from general to specific                                    |
|--------------|-------------------------------------------------------------------------------|
| Table data   | Theme default → table style → column style → column `.align()` or `.format()` |
| Table header | Theme default → table style → theme header → table header style               |
| Totals row   | Theme default → table style → theme total → totals-row style                  |
| Title block  | Theme default → title-level defaults → title style                            |

Later values override only the fields they set. For example, a table header style that sets `align="center"` keeps the
theme header's font and fill.

Here is the earlier reading list with those scopes applied:

```python
from caxton import col, sheet, spreadsheet, table, title, when, write

reading_list = spreadsheet(
    sheet(
        "Reading",
        title("Reading list", span=4, style="section-title"),
        table(
            source=books,
            columns=(
                text(source="title", title="Title"),
                date(source="published", title="Published").format(
                    date_format(variant="short"),
                ),
                money(
                    source="price",
                    title="Price",
                    currency="USD",
                    style="currency",
                ),
                percentage(source="progress", title="Read").format(
                    percentage_format(places=0),
                ),
            ),
            name="books",
            style="body",
            rules=(when(col("progress") >= 1, style="finished"),),
            auto_width=True,
        ),
    ),
    styles=library_styles,
    theme=library_theme,
)

write(reading_list, "reading-list.xlsx")
```

The conditional rule remains live in the workbook. The spreadsheet evaluates it for each data row and overlays the
`finished` style when the progress reaches 100 percent. Its formula refers to the semantic column id `progress`; moving
that column does not break the rule.

## Add an application-specific value

The built-in semantic set is extensible. Add a type when the application has a value with stable meaning that should be
visible to renderers, totals or inspection. A rating is one example:

```python
from typing import ClassVar

from caxton import Column, CustomFormat, SemanticType


class Rating(SemanticType):
    name: ClassVar[str] = "rating"
    numeric: ClassVar[bool] = True

    def default_format(self) -> CustomFormat:
        return CustomFormat(name="rating", pattern='0.0 "stars"')


rating = Column(
    semantic_type=Rating(),
    source="rating",
    title="Rating",
)
```

The type owns its default format and whether `Totals()` selects it automatically. Explicit `Total(...)` items are
validated by column identity; `numeric` is not a rejection rule for an explicitly named item. A renderer that supports
`semantic:extension` does not need a hard-coded `Rating` branch; both bundled XLSX renderers use the format declared by
the type. Keep custom business rules in the application rather than adding presentation state or backend objects to the
semantic type.

For the complete constructor surface, see
[`caxton.core.types`](../reference/types.md) and
[`caxton.core.formatting`](../reference/formatting.md).
