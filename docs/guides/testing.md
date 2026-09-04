# Testing documents

`caxton.testing` is a stable, pytest-independent API. It returns immutable public
values, including documented `caxton.core.ir` values where appropriate, but
never exposes mutable IR storage, parsers, diff algorithms or backend-native
objects.

Pick the narrowest level that observes the behaviour you care about.

| Level    | Function             | Reads rows?                 | Answers                          |
|----------|----------------------|-----------------------------|----------------------------------|
| Semantic | `inspect_spec()`     | Never                       | "Did I declare the right thing?" |
| Layout   | `inspect_layout()`   | Only with an explicit scope | "Where did the compiler put it?" |
| Artifact | `inspect_artifact()` | The render already happened | "What is actually in the file?"  |

## Semantic inspection

```python
from caxton.testing import inspect_spec

spec = inspect_spec(document)
sales = spec.worksheet("Sales").table("sales")

assert sales.column_ids == ("product", "revenue", "cost", "profit")
```

Structural, cheap, and safe for one-shot sources.

## Layout inspection

```python
from caxton.testing import Rows, inspect_layout

layout = inspect_layout(document, rows=Rows.sample(1))
sales = layout.worksheet("Sales").table("sales")

assert sales.anchor == "A3"
assert sales.row(0)["profit"] == Decimal(550)
```

The row scope is explicit:

| Scope            | Behaviour                                       |
|------------------|-------------------------------------------------|
| `Rows.none()`    | Structure only; no table row is read (default). |
| `Rows.sample(n)` | At most `n` rows per table.                     |
| `Rows.all()`     | Every row.                                      |

Grouped tables and matrices are always compiled through their single preparation
pass, because their shape depends on the complete source; the scope then controls
which of the compiled rows the view exposes.

Layout inspection is renderer-agnostic by default. Pass `backend="xlsxwriter"`
or `backend="openpyxl"` when the test must also prove that the selected backend
supports the document. Template-backed documents must be rendered and inspected
with `inspect_artifact()`, because their placement depends on workbook contents.

Charts, images and blocks are inspectable too:

```python
worksheet = inspect_layout(document).worksheet("Dashboard")

assert worksheet.block("block[0]").cell_range == "A1:B1"
assert worksheet.charts[0].series[0].values == "B4:B6"
assert worksheet.images[0].anchor == "A25"
```

## Artifact inspection

```python
from caxton.testing import inspect_artifact

artifact = inspect_artifact(write(document, target))
worksheet = artifact.worksheet("Sales")

assert worksheet.cell("C2").formula == "=A2-$B2"
assert worksheet.cell("C4").formula == "=SUM(C2:C3)"
assert worksheet.freeze_panes == "B2"
assert worksheet.merged_ranges == ("A2:A3",)
```

`inspect_artifact()` accepts a `RenderResult`, a path or raw bytes. Internally it
uses OpenPyXL, but the values it returns are plain immutable Caxton types.
For formula cells, both `value` and `formula` contain the formula text; inspection
preserves formulas instead of loading calculated cached values. When asserting
that a cell is absent, also assert a positive boundary such as
`worksheet.used_range` so a missing or displaced table cannot make the negative
assertion pass accidentally.

## Comparison and snapshots

```python
from caxton.testing import assert_spreadsheet_equal, canonical_snapshot

assert_spreadsheet_equal(actual_document, expected_document, check_metadata=False)

snapshot = canonical_snapshot(inspect_spec(document))
```

`assert_spreadsheet_equal()` takes documents or already-inspected specs, compares
them domain-aware, and reports differences instead of a raw object dump.
Inspecting a document for the comparison is structural and consumes no rows.

`canonical_snapshot()` serializes any testing value as deterministic JSON ending
in a single newline — suitable for committing next to a test.
Snapshot schema v2 uses fully qualified dataclass names and escapes mapping keys
that begin with `$`, preventing user data from colliding with snapshot tags.

## Property-based testing

With the `hypothesis` extra installed:

```python
from hypothesis import given

from caxton.testing import strategies as caxton_strategies


@given(caxton_strategies.spreadsheet_documents())
def test_documents_validate(document):
    validate(document)
```

Available strategies: `identifiers()`, `semantic_types()`, `columns()` and
`spreadsheet_documents()`.

## Testing one-shot sources

A one-shot test should prove *when* the source is first consumed and that a
second pass raises the focused error rather than quietly returning no rows:

```python
import pytest

from caxton import DataSourceConsumedError

rows = (row for row in SALES)
document = build(rows)

write(document, first_target)

with pytest.raises(DataSourceConsumedError):
    write(document, second_target)
```
