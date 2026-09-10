# Caxton Architecture

Caxton is a declarative document-generation library. Users describe a document's content and meaning; the compiler and
selected renderer turn that specification into an artifact. XLSX is the first supported format, but its engines and
constraints do not define the Core.

## Authority and delivered scope

This file is the normative source for the current architecture and its public boundaries. `AGENTS.md` translates those
boundaries into repository workflow. The README and examples demonstrate selected public flows. Design notes and use
case documents may explain the motivation for proposed APIs, but they do not expand the compatibility contract defined
here.

The supported document family is `SpreadsheetDocument`; the supported artifact profile is XLSX. The flow, tabular, and
fixed-layout families below define only extension boundaries. Their names in examples do not imply public constructors,
compilers, IRs, or renderers.

## Core invariants

- The public generative API creates immutable semantic nodes directly. There is no separate public builder graph, and
  fluent operations return a new node.
- The Semantic Model stores intent. Coordinates, layout decisions, execution state, caches, and backend-native objects
  live elsewhere.
- Nested collections are exposed as read-only values.
- Concrete presentation value objects are closed to subclassing. Applications customize presentation by composing those
  values directly or by returning them from application-owned functions.
- An entity `id` is separate from its value source (`source`) and label (`title`).
- Validation and compilation do not modify the Semantic Model.
- Each document family owns its model, validation, compiler, IR, and testing view. There is no universal super-model or
  super-IR.
- I/O belongs to operations and sinks, not to the document model.
- Formula intent (`col()`/`table_ref()`/`sheet_ref()`) covers references, arithmetic, and comparison. The Python
  row/aggregate layer computes conditional and lookup business logic (`IF`, `VLOOKUP`/`XLOOKUP`,
  `INDEX`/`MATCH`, and similar) before rendering. Caxton provides neither new formula node types for that logic nor an
  unvalidated raw-formula escape hatch. Business rules stay in Python, where they remain typed, tested, and reviewable.

Structural immutability does not imply universal hashability or repeatable execution: a semantic node can reference a
stateful or one-shot `DataSource`.

## Public boundaries and dependencies

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
└── _internal           orchestration, compilers, resolver, and backends
```

The allowed dependency direction is:

```text
api ───────→ core       testing ───→ core, _internal
api ───────→ _internal  _internal ─→ core
backends ──→ public core contracts
```

`core` does not import `api`, `_internal`, testing, or backend engines.
`_internal` does not import `api`. The public API does not return OpenPyXL, XlsxWriter, XML, or PDF canvas objects.
Mutable compiler passes, the resolver, caches, and execution plans are not compatibility contracts.

The public stability boundaries are:

- `caxton` is the recommended short facade and `caxton.api` is the extended generative API;
- `caxton.core` contains semantic models, value types, errors, protocols, renderer signature types, and versioned
  read-only IR contracts used by custom renderers;
- `caxton.testing` is the stable inspection and comparison surface;
- `caxton._internal`, including bundled renderer implementations, mutable IR builders, parsers, planners, and package
  post-processors, is not public API.

## Semantic Model and families

The common `Document` contract contains only shared semantics (`kind`, metadata). Families do not inherit capabilities
from one another:

| Family       | Semantics                          | Typical targets       |
|--------------|------------------------------------|-----------------------|
| Spreadsheet  | worksheets, grid, formulas, ranges | XLSX, ODS             |
| Flow         | sections, paragraphs, pagination   | DOCX, HTML, PDF       |
| Tabular      | schema and ordered records         | CSV, TSV, simple XLSX |
| Fixed layout | pages and positioned blocks        | PDF, SVG, images      |

Shared tabular data uses `TableData` (`schema` + `DataSource`). The visual
`SpreadsheetTable` and `FlowTable` remain family-specific nodes. Applications compose business concepts such as
`Receipt`, `Invoice`, or a specific `Report`
from neutral nodes; these concepts do not become Core families.

Automatic column sizing is backend-neutral presentation intent. `AutoWidth`
may bound a content-derived width with a positive minimum and maximum; an explicit column policy overrides its table
policy, while an explicit numeric width selected through the fluent API disables automatic sizing for that column.

Backend-independent semantic types include `Text`, `Integer`, `Decimal`,
`Boolean`, `Date`, `Time`, `DateTime`, `Duration`, `Money`, `Percentage`, and
`Link`. Users may extend this set. A custom `SemanticType` declares its `name`,
`numeric` flag, and requested display format. Any renderer that reports
`semantic:extension` can use that format without knowing the type. Formatting—alignment, border, color, font, display
format, and width hints—is stored separately from value semantics. The renderer controls the physical representation and
emits a capability diagnostic if it cannot preserve the semantics.

`Column(...)` is the generic constructor for built-in and application-defined semantic types. It creates the final
immutable Core node, normalizes convenient source and presentation inputs, and keeps `id`, `source`, and `title`
distinct. Type-specific factories are concise, backward-compatible conveniences that delegate to the same constructor.

`ColumnSchema` organizes ordinary `Column` values in the API layer. Its class body gives named declarations a canonical
order; inheritance may replace columns in place or append them. Consumers receive the schema as an immutable
`columns` tuple. The schema does not validate row data, and Core has no knowledge of it. Python literal expressions use
`literal()` alongside `field()`, `path()`, and `ref()` and remain separate from spreadsheet formulas.

## Pipeline

```text
Public API + raw inputs
    ↓  DataSource coercion without reading rows
Immutable Semantic Model
    ↓  structural validation
Requirement analysis → RequiredCapabilities + WorkbookOperation
    ↓  resolver checks the renderer descriptor and IR compatibility
Family compiler × selected renderer capabilities
    ↓
Versioned read-only Family IR
    ↓
Renderer → OutputSink → RenderResult
```

Requirement analysis is independent of the renderer. During lowering, the compiler resolves references, coordinates,
layout, and other physical decisions without writing them back to the model. The renderer serializes the agreed IR
version and owns the backend-specific execution plan.

`render()` uses a memory sink and returns `RenderResult`; `write()` normalizes a path, buffer, or another target into an
`OutputSink`. The system rejects an incompatible or ambiguous renderer before writing starts.

Built-in resolution considers, in order, an explicitly supplied renderer, backend, format, target extension or MIME
hints, document kind, required capabilities, workbook operation, and compatible IR versions. It selects a default only
when exactly one bundled route remains. Resolving the route never requires reading rows.

For a path target, orchestration owns a sibling staging transaction. It accumulates every renderer chunk there and
atomically replaces the target after the renderer succeeds. Delivery to a binary target also waits for successful
rendering. Seekable buffers are overwritten from offset zero and truncated; short writes are retried until the complete
artifact is delivered or a stable
`OutputError` is raised. A backend that accepts a seekable destination writes directly to the transaction-owned buffer,
avoiding a second staging copy.

## Data, computation, and streaming

The table declaration is `table(source=data, columns=(...))`. Both inputs are keyword-only: `source` defines the rows,
and `columns` defines their ordered semantic schema. This table-specific signature prevents confusion between a source
and a column sequence. Block factories with one primary value keep a positional first argument. A table coerces its
input to a public `DataSource`
once and stores that source instead of the original framework object or a materialized list.

Flat typed factories keep semantic identity, row access, and presentation in separate model properties. Every value has
an explicit origin through `source=`
or `formula=`. In the common exact-field case,
`text(source="name", title="Name")` uses `"name"` for both the top-level field name and semantic id. An explicit `id=`
overrides that identity and is required for callables, paths, expressions, aggregates, and formulas, whose sources have
no stable semantic name. Factory parameters remain keyword-only.

Built-in ingestion supports mappings, `NamedTuple`, dataclass and attribute objects, lazy iterables, and direct custom
`DataSource`/`RowAccessor`
implementations. Pydantic, ORM, and other frameworks stay outside the Core. DataFrame/Arrow-like inputs require a
separate batch contract.

Coercion recognizes an existing structural `DataSource` first, rejects DataFrame/Arrow-like and scalar/text/callable
inputs with a focused error, wraps single supported row objects, and otherwise adapts a lazy iterable. It does not use
`asdict`, `model_dump`, `vars`, `dir`, schema inference, or a global adapter registry. ORM/session lifecycle, eager
loading, projection, and prefetch remain the caller's responsibility.

Mapping access uses `row[field]`, while object access uses the exact attribute. Explicit `path(...)` defines nested
traversal. One semantic row evaluator handles callables and expressions. If an existing property or descriptor raises,
the error is preserved rather than reported as a missing field.

Python row expressions and spreadsheet formulas form separate semantic hierarchies. `field()` and `path()` read raw
data-source values; `ref()` reads the evaluated value of another semantic column. Caxton evaluates all three before
rendering. By contrast, `col()`, `table_ref()`, and `sheet_ref()` retain formula intent. `field()` cannot resolve a
column id, and `ref()` cannot read a row field, so their namespaces cannot be confused.

The `.transform(function)` expression applies ordinary typed Python business logic to one resolved `field()`/`path()`/
`ref()` value per row while keeping that input in the dependency graph. A literal is constant and provides no implicit
access to the current row. The compiler resolves formula semantic ids into cell/range nodes in the Spreadsheet IR; the
XLSX renderer materializes A1 or structured references. A Python expression cannot depend on a formula-backed column
because that column's value exists only in the artifact.

A range reference requires a known `row_count`. The compiler will not make a hidden pass over a one-shot or `UNKNOWN`
source to find the end of the range. Formula intent remains limited to references, arithmetic, and comparison: the
operations needed for a live value that recalculates when the artifact opens. Conditional branches and lookups stay in
the typed, tested Python row/aggregate layer rather than in formula text the compiler cannot inspect.

Backend-independent `AggregateExpr(function, expressions, where, default)`
represents aggregation intent. The initial execution adapter passes one Python value sequence per expression to an
arbitrary Python callable. It neither normalizes inputs nor removes `None`. An ungrouped aggregate uses the whole source
as one scope; a grouped table uses one leaf group per scope. If filtering leaves a scope empty, an explicit `default` is
returned without invoking the callable. Without a default, the callable controls empty-input behavior, and any failure
becomes an `AggregateEvaluationError`.

Grouping belongs to `SpreadsheetTable` columns rather than to a separate public
`GroupedTable`. Groups default to first-seen order, and the compiler derives exact row and merge ranges from resolved
hierarchical scopes. The physical declaration order of grouped columns determines the hierarchy. Dimension identity is
strict: Python value types are distinct, and `Decimal` scale is preserved. Thus `True`, `1`, `Decimal("1")`, and
`Decimal("1.0")` form separate groups. Sorted groups place `None` last in both ascending and descending order. Float
identity folds `-0.0` into `0.0` and treats every NaN as one canonical group.

`Matrix` is a spreadsheet-family block with typed row-dimension, column-dimension, and value columns. The convenience
factory normalizes accepted expressions into columns and uses the same `source=` keyword as tables. A bare string axis
names one exact top-level field, remains a `Text` dimension, and uses that string as its id. Dots have no path
semantics, and duplicate names receive deterministic numeric suffixes. Callers use `path(...)` for traversal. They use
an explicit column when semantic type, format, style, width, grouping, or a stable custom id matters.

The compiler discovers dynamic keys in first-seen order unless a dimension declares a grouping order. It uses the same
strict identity as table grouping and requires an `AggregateExpr` when multiple source values resolve to one cell.
Row-dimension merge intent produces vertical merges; flattened column headers reject merge intent. Generated value
columns expose their dimension key through the public testing layout, so tests need no compiler-generated ids.

Grouped tables and matrices buffer semantic input rows internally and consume
`ONE_SHOT` sources exactly once. Aggregate inputs are evaluated during that pass, after their filters, allowing the
original row object to be released before grouping. Once the dynamic axes are known, matrix output rows are emitted
lazily; sparse input does not require retaining the dense Cartesian output. These plans are not append-only streams.
Before rendering, prepared placements are checked against the XLSX sheet bounds of 1,048,576 rows by 16,384 columns.
`DataSource` remains responsible for row ingestion alone and has no `groupby`, pivot, or aggregation operations.

## Spreadsheet block layout

A worksheet holds a closed set of spreadsheet blocks: `SpreadsheetTable`,
`Matrix`, `Title`, `Spacer`, `Image`, `Chart`, and the `Stack` flow container. Blocks carry intent; the compiler owns
placement. Before building any IR node, a dedicated layout pass walks the blocks in declaration order, measures each
one, and assigns its physical anchor and occupied range. Ordinary-table measurements are structural: one header row, a
non-consuming `row_count`, and an optional footer row. Grouped tables and matrices are measured from their single-pass
prepared results because their output shapes differ from their inputs. Titles occupy one row. Images and charts convert
their declared pixel size into whole cells.

An explicit `anchor` is the placement escape hatch. An anchored block keeps its declared position and still advances the
flow cursor, preventing the next implicit block from landing inside it. Before consuming any source, validation reports
overlaps between statically measurable blocks as `block_overlap`
issues—even if the worksheet also contains a shape-dependent grouped table or matrix. Prepared shapes receive a second
placement check before rendering.

If a table's height is unknown, the flow cursor becomes invalid instead of guessing. The next implicit block raises
`UnsupportedFeatureError`; the document still works when every subsequent block has an explicit anchor.

Because structural validation does not consume rows, a clean `validate()`
result cannot guarantee a clean render for shape-dependent blocks. Grouped-table or matrix preparation can consume a
`ONE_SHOT` source before the second placement check discovers an overlap; after that failure, the source remains
consumed.

Charts bind to data through `table_ref(...)` plus semantic column ids. The compiler resolves them into physical ranges
of the placed table, so a chart, like a range reference, requires a known `row_count`.

A source declares its repeatability as `REITERABLE`, `ONE_SHOT`, or `UNKNOWN`. Coercion and structural validation do not
read rows. A second pass over a one-shot source raises `DataSourceConsumedError`, and an unknown source cannot be read
again implicitly. A multi-pass feature is either rejected before writing or uses an explicit, documented buffering
policy. Data validation and semantic inspection do not read rows implicitly. Ordinary layout inspection reads rows only
under an explicit `sample` or `full` scope. Grouped-table and matrix layout compilation still uses its documented
single-pass buffer because shape resolution requires the complete source.

An error while retrieving the next row from an iterator is a
`DataSourceIterationError`, not a backend failure, and it preserves the index of the next row and the original cause.

## Renderer and XLSX

The public `Renderer` accepts a versioned family IR, an `OutputSink`, and a
`RenderContext`. Its descriptor declares family and IR versions, formats, MIME types and extensions, workbook
operations, capabilities, and execution modes. A custom renderer can be passed directly without importing `_internal`.
This release has no global provider registry or entry-point discovery.

The types state two IR contracts. Table rows are a one-shot
`RowStream`: a second pass raises instead of silently yielding nothing, while
`materialized()` creates an explicitly re-readable copy. Resolved formulas form the closed `ResolvedFormulaNode` union,
which a renderer can match exhaustively.

For XLSX, the workbook operation is determined before adapter selection:

| Operation                  | Adapter                                               |
|----------------------------|-------------------------------------------------------|
| `CREATE_NEW_WORKBOOK`      | default `XlsxWriterRenderer`                          |
| explicit legacy create-new | `OpenpyxlRenderer`                                    |
| `USE_EXISTING_TEMPLATE`    | dedicated `OpenpyxlTemplateRenderer` after inspection |

The template pipeline builds a read-only `TemplateContext` and passes it to the family compiler. A template operation
cannot silently fall back to create-new. Constant-memory/write-only is a renderer execution plan with verifiable
capabilities, not a separate document type. Backend hooks and post-processing are explicit, namespaced, and absent from
the Core model.

The XLSX adapter resolves generic `ref(...)` template targets through defined names scoped to a workbook or worksheet. A
normal target is a data-only region. A `repeat(slot(...))` target copies the named block once per semantic row,
including its styles, translated relative formulas, and contained merges. The renderer works on a private workbook copy
and writes to the sink only after rendering, hooks, and ordered XLSX package post-processing succeed. Pivot package
paths and relationships remain backend-local descriptor data.

Template targets replace mapped data across the named range. Unused old rows, literal values, and hyperlinks are
cleared; styles and formulas in columns outside the semantic table remain template-owned. Target rows are materialized
once before final placement validation. Their actual shape is needed for both target-height checks and detection of a
repeated block growing into another semantic placement.

OpenPyXL does not update every dependent workbook structure when it inserts rows, so repeated blocks reject downstream
formulas or workbook structures that cannot be shifted safely. The data-only target route rejects presentation intent it
cannot preserve before preparing rows. A portable empty native table owns one blank data row; an optional semantic
footer follows that row and lies outside the native table range.

XLSX materialization preserves the semantic distinction between literal text, formulas, and links. Both bundled adapters
reject values that XLSX cannot represent portably: non-finite numbers; integers or decimals beyond Excel's 15
significant digits, ignoring insignificant trailing zeroes; overlong cell text; binary cell values; and timezone-aware
date/time values. The resulting error has stable semantic context rather than a backend-specific failure or silent
coercion.

Caxton ships as a single distribution. XlsxWriter and OpenPyXL are part of the base runtime dependencies, but they do
not form a shared rendering pipeline:
the built-in XLSX artifact inspector also uses OpenPyXL. Official backends ship with `caxton`; they do not use separate
packages.

## Delivered spreadsheet/XLSX profile

The current feature boundary includes:

| Area                          | Delivered behavior                                                                                                                                         |
|-------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Tables and values             | typed columns, mappings and Python row objects, Python expressions, semantic value normalization, explicit and bounded automatic widths                    |
| Spreadsheet expressions       | semantic cell/range and cross-sheet formulas, conditional formatting, totals, and named table references                                                   |
| Data shaping                  | hierarchical grouping, arbitrary Python aggregates with filters/defaults, and dynamic matrix axes with duplicate-cell conflict detection                   |
| Presentation                  | reusable styles/themes, multiple worksheets, filters, freeze panes, titles, spacers, stacks, images, and charts bound to named tables                      |
| Layout                        | flow placement, explicit A1 anchors, overlap detection, merge ranges, sheet-bound checks, and post-preparation placement checks for shape-dependent blocks |
| Execution                     | standard and constant-memory create-new plans, one-shot protection, atomic file output, binary targets, and stable capability diagnostics                  |
| Templates and XLSX extensions | named-range targets, repeated template blocks, pivot cache refresh, namespaced OpenPyXL hooks, and ordered backend-local package post-processing           |
| Testing                       | semantic inspection/diff, canonical snapshots, explicit-scope layout inspection, XLSX artifact inspection, and optional Hypothesis strategies              |

Charts currently bind to an existing named table; an independent inline chart
`data=` source is not part of the public API. A reusable Python factory can construct a fresh immutable specification,
but bind-time `source_ref()` and
`bind()` placeholders are not implemented.

## Validation, diagnostics, and testing

Validation has three levels: construction-time local invariants, structural cross-node rules that do not read data, and
explicitly requested data validation. Structural validation rejects direct and indirect dependency cycles formed by
Python `ref()` expressions or formula
`col()`/`table_ref()`/`sheet_ref()` references, including cycles across worksheets. The diagnostic includes the cycle's
complete closed semantic path. Like overlap validation, cycle detection consumes no row data and finishes before
requirement analysis or compilation.

These structural issues originate from `CyclicReferenceError`.
`CyclicColumnError` remains the row evaluator's defensive failure if that internal boundary is invoked without
validation. All library errors inherit from `CaxtonError`. Public categories distinguish validation, data
source/evaluation, invalid operation, unsupported feature, and render/backend failures. Output delivery failures use
`OutputError`.

Errors contain a semantic path and an immutable structured-context snapshot; exception chaining preserves the original
cause. Multiple validation issues are aggregated, while non-fatal issues use `warnings` categories. Type and value
errors in the public construction API use the Python-compatible `TypeError` and
`ValueError` subclasses `CaxtonTypeError` and `CaxtonValueError`, so callers may also catch them through `CaxtonError`.

`caxton.testing` is a stable, pytest-independent API with three levels:

- semantic inspection by IDs, domain-aware comparison, and canonical snapshots;
- read-only family layout inspection with an explicit row scope;
- backend-neutral inspection of a completed artifact.

The XLSX inspector uses OpenPyXL only inside the implementation and returns immutable public values. The public API does
not expose internal IR storage, parsers, or diff algorithms.

## Extension

- A new operation is added as a function, not as a method on every semantic node.
- Direct custom objects use small structural protocols without a registry.
- A new backend implements the public renderer contract and accepts the existing IR.
- A new family adds its own model/compiler/IR without extending the other families.
- Reusable column schemas may supply ordinary columns to a future family only where that family explicitly supports
  their semantic and presentation intent; schema reuse does not imply universal family portability.
- Conversion between families uses an explicit `DocumentConverter` and returns a loss report; changing the backend
  within a family remains a render operation.
- Registries, discovery, pass managers, and universal hook systems appear only with a validated use case.

## Deliberate deferrals

The following are architectural extension points or proposals, not current public promises:

- Flow, tabular, and fixed-layout models, their IRs and renderers, including CSV, DOCX, HTML, PDF, SVG, and image
  outputs;
- cross-family `DocumentConverter` and loss reports;
- schema inference, `BatchDataSource`, async sources, framework-specific source adapters, and public source/type-adapter
  registries;
- bind-time data placeholders, inline chart data, and a universal testing contract spanning semantic, layout, and
  artifact views;
- entry-point discovery, provider priority/conflict resolution, compiler pass managers, global hook/event registries,
  and universal extension managers.

A deferred item becomes part of the contract only when a concrete public use case, implementation, focused tests,
examples, and this file agree. Names or sketches in design documentation do not reserve a public API.
