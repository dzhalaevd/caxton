# Composing spreadsheet reports

Use `compose()` when several independently constructed reports should become sections
of one workbook:

```python
from caxton import compose, render

sections = {
    "Parameters": build_parameters_report(parameters),
    "Vulnerabilities": build_vulnerabilities_report(vulnerabilities),
    "Secrets": build_secrets_report(secrets),
}

document = compose(
    sections,
    theme=REPORT_THEME,
    styles=REPORT_STYLES,
)
xlsx = render(document, backend="xlsxwriter").data
```

Mapping insertion order is preserved. If a child contains worksheets named `Summary`
and `Details`, the `Parameters` section contributes `Parameters - Summary` and
`Parameters - Details`. Explicit `sheet_ref()` references between worksheets of the
same child document are updated automatically.

Composition returns a normal immutable `SpreadsheetDocument`; it does not render,
validate, or read table rows. This makes it safe for lazy and one-shot sources.

## Deciding which sections to include

A document with no worksheets contributes nothing. A worksheet containing a table
whose row source happens to be empty still contributes that worksheet, because probing
the source would break lazy execution. Make the application-level decision before
calling `compose()`:

```python
sections = {}

if parameters.rows:
    sections["Parameters"] = build_parameters_report(parameters)
if vulnerabilities.rows:
    sections["Vulnerabilities"] = build_vulnerabilities_report(vulnerabilities)

document = compose(sections)
```

If no worksheets remain, `compose()` raises `CaxtonValueError`.

## Names and workbook settings

Worksheet names are section-qualified, but table and style names remain
workbook-global. Give reusable section builders globally stable table names such as
`parameter_issues` and `vulnerability_issues`; ordinary `validate()` reports duplicate
table names.

Equal child styles, themes, and metadata are coalesced. Conflicting child values fail
closed unless the call supplies the corresponding outer `styles=`, `theme=`, or
`metadata=` value. Child documents cannot own templates; pass one `template=` for the
final workbook instead.

Explicit worksheet references must stay within their child document. `compose()`
rejects unresolved references rather than guessing that they point into another
section.
