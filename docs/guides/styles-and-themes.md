# Styles and themes

Presentation vocabulary is backend-neutral: you describe fonts, fills, borders
and alignment, and the renderer materializes them.

## Inline styles

```python
from caxton import FontStyle, Style

Style(
    font=FontStyle(name="Arial", size=11, bold=True, color="#004B8D"),
    fill="#D9EAF7",
    align="center",
    border_bottom="thin",
)
```

`Style` accepts both structured and shorthand fields:

| Structured  | Shorthand                                                       |
|-------------|-----------------------------------------------------------------|
| `font`      | `font_color="#RRGGBB"`                                          |
| `fill`      | `fill="#RRGGBB"` (a bare string becomes a solid `FillStyle`)    |
| `alignment` | `align="left" \| "center" \| "right"`                           |
| `border`    | `border_top` / `border_right` / `border_bottom` / `border_left` |

Border sides accept a style name (`"thin"`, `"medium"`, `"thick"`, `"dashed"`,
`"dotted"`, `"double"`) or a `BorderLine` with its own color. Colors must use
`#RRGGBB` notation; anything else raises `CaxtonValueError`.

`CellAlignment` adds vertical alignment and text wrapping:

```python
from caxton import CellAlignment, Style

Style(alignment=CellAlignment(horizontal="center", vertical="top", wrap_text=True))
```

## Reusable named styles

Declare a `StyleSheet` on the document and reference styles by name anywhere a
style is accepted:

```python
from caxton import Style, StyleSheet, decimal, decimal_format, sheet, spreadsheet, table

report = spreadsheet(
    sheet(
        "Sales",
        table(source=rows, columns=(decimal(source="price", style="number"),)),
    ),
    styles=StyleSheet(
        {
            "number": Style(display_format=decimal_format(grouping=True)),
            "positive": Style(fill="#C6EFCE", font_color="#006100"),
        },
    ),
)
```

A plain mapping works too — `styles={"number": Style(...)}` is normalized into a
`StyleSheet`.

## Themes

A `DocumentTheme` supplies document-wide defaults for ordinary cells, header
rows and totals rows:

```python
from caxton import DocumentTheme, FontStyle, Style

DocumentTheme(
    default=Style(font=FontStyle(name="Calibri")),
    header=Style(font=FontStyle(bold=True)),
    total=Style(font=FontStyle(bold=True)),
)
```

Applications can package a reusable branded theme in an ordinary function. The
function still returns the exact value type understood by Caxton instead of
introducing a theme subclass whose additional state would be ignored:

```python
from caxton import DocumentTheme, FontStyle, Style


def acme_theme() -> DocumentTheme:
    return DocumentTheme(
        default=Style(font=FontStyle(name="Arial")),
        header=Style(
            font=FontStyle(name="Arial", bold=True, color="#FFFFFF"),
            fill="#004B8D",
        ),
        total=Style(font=FontStyle(name="Arial", bold=True)),
    )
```

Presentation value objects are closed to subclassing. Compose them directly or
return them from application-owned functions when reusable defaults are needed.

## Resolution order

Styles are layered, most general first:

```text
theme default → theme role (header / total) → table style → column style → conditional rule
```

Later layers override individual fields rather than replacing the whole style,
so a column that only sets a display format keeps the theme's font.

## Conditional styles

Conditional rules are evaluated by the spreadsheet, not by Caxton, so they stay
live in the finished file:

```python
from caxton import col, when

table(
    source=rows,
    columns=(decimal(source="delta"),),
    rules=(when(col("delta") > 0, style="positive"),),
)
```

The rule's `style` may be an inline `Style` or a name from the document
stylesheet.
