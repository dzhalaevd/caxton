# XLSX templates

Instead of creating a workbook from scratch, Caxton can fill an existing one.
Your designers keep owning the styling, print setup and formulas; Caxton only
supplies data into named regions.

## Declaring a template

```python
from caxton import spreadsheet, template

report = spreadsheet(
    sheet("Monthly Report", data_table),
    template=template("assets/monthly_sales_template.xlsx"),
)
```

`template()` describes intent — it does **not** open the file. The format is
detected from the path suffix, or from the package content types when you pass
bytes. Pass `format="xlsx"` to state it explicitly; a conflict between the
declared and detected format raises `TemplateFormatError`.

```python
template(uploaded_bytes, format="xlsx")
```

## Targeting a named range

A table declares where it goes with `into=`, using a workbook- or
worksheet-scoped defined name:

```python
from caxton import date, decimal, integer, ref, table, text

data_table = table(
    source=ROWS,
    columns=(
        date(source="date"),
        text(source="product"),
        text(source="region"),
        integer(source="quantity"),
        decimal(source="unit_price"),
    ),
    into=ref("report_data"),
)
```

A plain `ref(...)` target is a **data-only** region: values are written into the
named range and the surrounding template is untouched.

`into` and `anchor` are mutually exclusive — a template target already says where
the data goes.

## Repeating a template block

`repeat(ref(...))` copies the named block once per semantic row, including its
styles, contained merges and relative formulas (translated for each copy):

```python
from caxton import ref, repeat, table

table(source=ROWS, columns=columns, into=repeat(ref("line_item")))
```

## What the renderer guarantees

- The template pipeline builds a read-only `TemplateContext` first, then hands it
  to the family compiler.
- A template operation never silently falls back to creating a new workbook.
- The renderer works on a private copy of the workbook. Your source template file
  is never modified.
- Output is written to the sink only after rendering, hooks and ordered XLSX
  package post-processing all succeed.

Unresolvable targets raise focused errors: `MissingTemplateRefError`,
`AmbiguousTemplateRefError`, `IncompatibleTemplateRefError` and
`InvalidTemplateRefError`.

## XLSX escape hatches

Backend-specific extensions live in `caxton.api.xlsx`, are namespaced, and never
appear in the core model.

### OpenPyXL hooks

```python
from caxton import spreadsheet, template
from caxton.api import xlsx


def configure_print_area(context: xlsx.OpenpyxlHookContext) -> None:
    context.native_sheet.print_area = "A1:F27"


spreadsheet(
    sheet("Monthly Report", data_table),
    template=template(
        SOURCE,
        extensions=(xlsx.openpyxl_hook(configure_print_area, sheet="Monthly Report"),),
    ),
)
```

The hook receives narrow access to the native workbook and sheet, runs after
semantic content is rendered, and declares the capability it needs so an
incompatible renderer fails early.

### Pivot rebinding

```python
from caxton import ref
from caxton.api import xlsx

xlsx.pivot("SalesPivot", source=ref("report_data"), refresh_on_open=True)
```

This rebinds an existing pivot cache in the template to generated data. Pivot
package paths and relationships stay backend-local descriptor data.

!!! note

    Anything reached through a hook is, by definition, outside the
    backend-neutral contract. Keep hooks small and specific.
