# Testing and diagnostics

A spreadsheet can be wrong before any row is read, while values are evaluated, after layout is resolved or only in the
finished XLSX file. Test the narrowest layer that can prove the behavior you care about. The failure then points to one
part of the document pipeline instead of arriving as an unexplained export error.

| Layer      | Public operation                         | Reads rows?                                      | Use it to check                              |
|------------|------------------------------------------|--------------------------------------------------|----------------------------------------------|
| Structure  | `validate()`                            | No                                               | References, names, anchors and model rules   |
| Semantics  | `inspect_spec()`                        | No                                               | Declared worksheets, tables, columns, styles |
| Layout     | `inspect_layout()`                      | Only under the requested scope, with exceptions | Placement, evaluated values, resolved formulas |
| Artifact   | `inspect_artifact()`                    | Rendering has already read the source            | Cells, XLSX tables, formats and workbook behavior |

The examples use a small catalog with an explicit anchor so each layer has something useful to observe:

```python
from caxton import integer, sheet, spreadsheet, table, text

catalog = spreadsheet(
    sheet(
        "Catalog",
        table(
            source=(
                {"title": "Kindred", "pages": 288},
                {"title": "Piranesi", "pages": 272},
            ),
            columns=(
                text(source="title", title="Title"),
                integer(source="pages", title="Pages"),
            ),
            name="books",
            anchor="B2",
        ),
    ),
)
```

## Check the declaration before reading rows

Public factories enforce local invariants when a node is constructed. A value of the wrong runtime type raises
`CaxtonTypeError`; a value that is well typed but invalid raises `CaxtonValueError`. Both also inherit from Python's
`TypeError` and `ValueError`.

`validate()` handles rules that need the complete semantic graph: duplicate ids and names, missing references, reference
cycles, invalid anchors and overlaps between statically measurable blocks. It collects related problems into one
`ValidationError` and does not inspect the row source.

```python
from caxton import validate
from caxton.testing import inspect_spec

validate(catalog)

spec = inspect_spec(catalog)
books = spec.worksheet("Catalog").table("books")

assert books.anchor == "B2"
assert books.column_ids == ("title", "pages")
assert books.column("pages").semantic_type.name == "integer"
```

Semantic inspection is the right default for document builders and reusable sections. It observes declared intent, is
safe for generators and returns immutable public values. `assert_spreadsheet_equal()` compares those values with
semantic paths in its differences; `canonical_snapshot(inspect_spec(document))` gives a deterministic JSON snapshot
when a broader contract is worth keeping.

A successful `validate()` does not promise that every row can be evaluated. It also cannot know the final size of a
grouped table or matrix without reading its source. Those checks belong to the next layer.

## Inspect layout when coordinates or values matter

`inspect_layout()` runs validation, compilation and layout without creating an XLSX package. Row access is explicit:

| Scope            | Ordinary table behavior                                  |
|------------------|----------------------------------------------------------|
| `Rows.none()`    | Resolve structure and placement without reading rows.    |
| `Rows.sample(n)` | Read and expose at most `n` rows from each table.         |
| `Rows.all()`     | Read and expose every row.                                |

```python
from caxton.testing import Rows, inspect_layout

layout = inspect_layout(catalog, rows=Rows.sample(1))
books = layout.worksheet("Catalog").table("books")

assert books.anchor == "B2"
assert books.column("pages").header_address == "C2"
assert books.row(0)["pages"] == 288
```

Pass `backend="xlsxwriter"` or `backend="openpyxl"` when the test must also prove that a bundled renderer supports the
document. Without `backend=`, layout inspection stays renderer-independent.

There are two deliberate exceptions to the row-scope table. Grouped tables and matrices must consume their complete
source once because their output shape depends on the data. `Rows.none()` hides their rows from the returned view but
does not skip that preparation pass. Template placement depends on an existing workbook, so `inspect_layout()` rejects
template-backed documents; render them and inspect the artifact instead.

## Inspect the file when XLSX behavior matters

Artifact inspection answers questions the semantic model and layout cannot: whether a native table has the expected
range, whether a formula was serialized correctly, which number format reached the cell, and whether a template feature
survived the write.

```python
from caxton import render
from caxton.testing import inspect_artifact

result = render(catalog)
artifact = inspect_artifact(result)
worksheet = artifact.worksheet("Catalog")

assert worksheet.table("books").cell_range == "B2:C4"
assert worksheet.cell("B3").value == "Kindred"
assert worksheet.cell("C3").value == 288
```

`inspect_artifact()` accepts a `RenderResult`, a path, raw bytes or a readable binary object. It uses OpenPyXL internally
for XLSX parsing but returns immutable Caxton values rather than native workbook objects. A malformed or truncated file
raises `ArtifactInspectionError`; that describes the artifact being inspected, not a failure from the renderer that may
have produced it elsewhere.

For a negative assertion, include a positive boundary. Checking that `A1` is empty can pass when an entire table moved
to the wrong place; checking `worksheet.used_range` or the expected table range makes the test meaningful. Template
features deserve a small intentional input workbook and an artifact assertion on the property that must survive.

## Treat one-shot sources as test resources

A generator belongs to the document that captured it. Structural validation and semantic inspection leave it untouched.
Ordinary layout inspection with `Rows.none()` does too. A sampled layout inspection or a render starts the one permitted
pass, and a second attempt raises `DataSourceConsumedError` instead of returning an empty table.

```python
from collections.abc import Iterator

import pytest

from caxton import (
    DataSourceConsumedError,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    validate,
)
from caxton.testing import inspect_layout, inspect_spec

events: list[str] = []


def book_rows() -> Iterator[dict[str, str]]:
    events.append("read")
    yield {"title": "Kindred"}


document = spreadsheet(
    sheet(
        "Catalog",
        table(
            source=book_rows(),
            columns=(text(source="title", title="Title"),),
        ),
    ),
)

validate(document)
inspect_spec(document)
inspect_layout(document)
assert events == []

render(document)
assert events == ["read"]

with pytest.raises(DataSourceConsumedError):
    render(document)
```

When semantic, layout and artifact tests all need data, give each phase a freshly built document or materialize the rows
once into a tuple. Do not reuse a generator merely because the first inspection requested only a sample: opening the
source is already its single pass. The same rule applies after a failed render if the failure occurred after row reading
began.

## Locate the stage that failed

Caxton's exception categories follow pipeline boundaries. Start with the category, then read its path, context and
original cause.

| Failure area | Typical exception | What it says | First place to look |
|--------------|-------------------|--------------|---------------------|
| Document construction | `CaxtonTypeError`, `CaxtonValueError` | One public argument violates a local invariant. | The factory call that raised. |
| Structural validation | `ValidationError` | One or more declarations conflict before data access. | `error.issues`, especially each issue's `path`, `code` and `context`. |
| Data ingestion or evaluation | `DataSourceError` | A source was reused, iteration failed, a field was absent, or row computation failed. | `row_index`, field or column context, then `error.__cause__`. |
| Template inspection or binding | `TemplateError` | The workbook format or a named target is missing, ambiguous, malformed or incompatible. | The template fixture and semantic `slot()` or repeated region. |
| Renderer selection or capability | `UnsupportedFeatureError`, `RenderError` | No compatible route can represent the requested format, mode or feature set. | Requested backend, format, execution mode and document feature. |
| Backend execution | `BackendError` | The selected spreadsheet engine failed while materializing the IR. | `context["backend"]` and the chained engine exception. |
| Delivery | `OutputError` | Staging, writing, flushing or committing the artifact failed. | `context["operation"]`, target details and the chained I/O exception. |

This separation prevents a broken iterator from looking like an XlsxWriter failure. `DataSourceIterationError` records
the index of the row Caxton tried to obtain and keeps the iterator's exception as `__cause__`. `MissingFieldError`
identifies an absent field; `FieldAccessError` means the field exists but its property or descriptor raised. Aggregate,
grouping and matrix failures likewise remain data errors even when they surface during `render()`.

Template, backend and output errors are all rendering concerns, but they call for different fixes. A `TemplateError`
belongs to the input workbook contract. A `BackendError` belongs to renderer execution. An `OutputError` means the
artifact could not reach its destination; it is not wrapped as a backend failure. Path delivery is atomic, so a failure
before commit leaves the previous file intact. See [Rendering and delivery](render.md) for the path and buffer guarantees.

## Use structured exceptions in tests and logs

Every operational exception in `caxton.core.errors` derives from `CaxtonError`. Its human-readable `message` is useful
in a traceback, while `path` and the immutable `context` mapping are stable inputs for assertions and structured logs.
Wrapper errors preserve the implementation exception through ordinary Python exception chaining. Testing selectors and
comparisons use ordinary `LookupError` and `SpreadsheetAssertionError` because they describe failed test expectations.

`ValidationError` is the main special case because it can report several problems at once:

```python
import pytest

from caxton import ValidationError, ref, sheet, spreadsheet, table, text, validate

invalid_document = spreadsheet(
    sheet(
        "Catalog",
        table(
            source=(),
            columns=(
                text(source="title"),
                text(id="title", source="alternate_title"),
                text(id="shelf", source=ref("missing")),
            ),
        ),
    ),
)

with pytest.raises(ValidationError) as captured:
    validate(invalid_document)

assert {issue.code for issue in captured.value.issues} == {
    "ColumnNotFoundError",
    "DuplicateColumnError",
}
assert all(issue.path is not None for issue in captured.value.issues)
```

Prefer the specific category that matches the behavior under test. At an application boundary, catch `CaxtonError` to
add logging or translate it into a transport error, then retain the concrete type, `path`, `context` and `__cause__`.
String matching throws away the information that distinguishes a bad row from a bad template or an unwritable target.

Warnings use the parallel `CaxtonWarning` hierarchy. Filter a specific category such as `PerformanceWarning` when a test
must reject an expensive path; do not treat every document warning as a rendering failure.

The exhaustive class lists live in [`caxton.core.errors`](../reference/errors.md), while the immutable inspection and
comparison types are documented in [`caxton.testing`](../reference/testing.md).
