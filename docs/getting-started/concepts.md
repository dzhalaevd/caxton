# Core concepts

## The document is a value

Every public factory returns a frozen node, and every fluent method returns a
*new* node rather than mutating the receiver:

```python
from caxton import text

base = text(source="product")
titled = base.titled("Product")

assert base is not titled
```

Because nothing is mutable, one factory function can produce many documents from
different row sets without copying a shared graph.

## Intent, not coordinates

The semantic model stores *what you meant*. It never stores cell addresses,
layout decisions, execution state, caches or backend objects. Those belong to
the compiler and the renderer, and are not part of the compatibility contract.

This is why `table(...)` has an optional `anchor` (declared intent) but no
"current row" (resolved state).

## The three namespaces

Caxton keeps three ways of producing a value strictly separate.

| Namespace            | Built with                            | Evaluated by    | Ends up in the artifact as |
|----------------------|---------------------------------------|-----------------|----------------------------|
| Row fields           | `field()`, `path()`                   | Caxton          | A literal value            |
| Semantic columns     | `ref()`                               | Caxton          | A literal value            |
| Spreadsheet formulas | `col()`, `table_ref()`, `sheet_ref()` | The spreadsheet | A live formula             |

`field()` never resolves a column id and `ref()` never reads a row field, so the
two cannot be confused. A Python expression cannot depend on a formula-backed
column, because that column's value only exists once the file is opened.

See [Formulas and references](../guides/formulas-and-references.md).

## Identity, source and title are separate

A column's `id` is its semantic identity, used by `ref()`, `col()`, totals,
charts and the testing views. It is independent of:

- `source` — where the raw value comes from;
- `title` — what a human sees in the header.

```python
from caxton import field, money

money(id="net", source=field("net_amount"), title="Net revenue")
```

## Data is lazy and its repeatability matters

`table()` coerces its input into a `DataSource` once. Construction, structural
validation and semantic inspection never read a row.

A source declares itself as one of:

- `REITERABLE` — can be iterated again (e.g. a tuple or list);
- `ONE_SHOT` — a generator or cursor that can be consumed exactly once;
- `UNKNOWN` — repeatability cannot be determined.

A second pass over a one-shot source raises `DataSourceConsumedError` instead of
silently yielding nothing. Features that would need an extra pass are rejected
before writing, or documented as buffering exactly once (grouped tables and
matrices).

## The pipeline

```text
Public API + raw inputs
    ↓  DataSource coercion, without reading rows
Immutable semantic model
    ↓  structural validation
Requirement analysis → capabilities + workbook operation
    ↓  resolver checks the renderer descriptor and IR compatibility
Family compiler × selected renderer capabilities
    ↓
Versioned read-only spreadsheet IR
    ↓
Renderer → OutputSink → RenderResult
```

Requirement analysis does not depend on the renderer, and renderer selection
happens *before* the target file is opened. `render()` uses a memory sink;
`write()` normalizes a path or buffer into a sink and, for paths, replaces the
destination atomically only after the backend succeeds.

## Public boundaries

```text
caxton                 short public facade
├── api                 factories and render/write/validate
├── core
│   ├── models          immutable semantic nodes
│   ├── types           semantic value types
│   ├── formatting      backend-neutral presentation vocabulary
│   ├── protocols       DataSource, Renderer, and other contracts
│   ├── ir              versioned read-only family IR
│   └── errors
├── testing             public inspection and comparison API
└── _internal           orchestration, compilers, resolver, backends
```

`caxton._internal` — including the bundled renderers — is **not** public API.
Import from `caxton`, `caxton.api`, `caxton.core.*` or `caxton.testing` only.

Full detail lives in [Architecture](../architecture.md).
