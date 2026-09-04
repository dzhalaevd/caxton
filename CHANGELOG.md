# Changelog

<!-- towncrier release notes start -->

## [0.2.3] - 2026-09-04

### Breaking changes

- Spreadsheet tables now use the single keyword-only
  `table(source=..., cols=(...))` form. Typed column factories are available only
  through the explicit `column.<type>(id=..., source=..., title=...)` namespace;
  the positional table form and flat typed-factory exports have been removed.

  Matrix dimensions also accept raw field names, and all declarations continue to
  produce the same immutable semantic nodes before compilation. ([#24](https://github.com/dzhalaevd/caxton/issues/24))
- Harden `caxton.testing` comparisons, callable identities, layout preflight, and
  XLSX inspection against false positives. Canonical snapshots now use schema v2,
  with fully qualified dataclass names and escaped `$` mapping keys.
- Remove the shallow ``CorporateTheme`` subclass. Compose branded defaults with
  ``DocumentTheme`` directly or return one from an application-owned function;
  concrete presentation value objects are now marked as final for type checkers.
- Template targets are now their own type. `into=` and `xlsx.pivot(source=...)`
  take `slot("name")`, which names a region of the template document; `ref()` is
  again only a row expression naming a semantic column.

  Table rows in the spreadsheet IR are a `RowStream` consumed exactly once. A
  second pass raises `InvalidOperationError` instead of silently yielding nothing,
  and a renderer that needs two passes calls `materialized()` for a re-readable
  copy. Resolved formulas form the closed `ResolvedFormulaNode` union, and the
  `ResolvedFormula` base can no longer be instantiated.

  Two silent resolutions became errors: a column that sets both an explicit width
  and an auto-width policy, and a `money(currency=...)` column formatted with a
  display format that cannot show a currency.

### Features

- Semantic types are an open set. A user-defined `SemanticType` declares its
  `name`, its `numeric` flag and the display format it asks for, and any renderer
  reporting the `semantic:extension` capability — both bundled XLSX backends —
  renders it without recognizing the type.

  The public surface gained what typed code needs: the return types of every
  public factory, the `RowSourceInput` alias for `table(source=...)`, and the
  `DefaultRowAccessor`, `MappingRowAccessor` and `AttributeRowAccessor` helpers,
  so a third-party `DataSource` only implements `iter_rows`. XLSX extension
  intents moved out of `caxton._internal` and `caxton.api.xlsx` now re-exports
  them from the model. `Notification.raise_if_errors` takes the error class to
  raise.

  `RenderResult.content` and the per-axis flags of `relative()` are deprecated.
  Error context is now printed with the error, and image sources that cannot be
  read report their path.

### Bug fixes

- Make public construction errors consistently catchable through ``CaxtonError``,
  restore copy and pickle support for errors, and correct immutable value semantics
  for styles, themes, capabilities, and spreadsheet IR validation.
  Presentation value types now also report ``__final__`` on Python 3.10, because
  ``final`` comes from ``typing_extensions`` there.
- Preserve literal XLSX text and portable numeric fidelity, make path and buffer
  writes transactional without redundant XlsxWriter staging, and validate the
  actual prepared extent of template targets before mutating a workbook. Template
  targets now clear stale literal values and hyperlinks throughout their named
  range while preserving template-owned formulas outside the semantic columns.
  Empty native tables keep an optional totals footer outside the table range.

  Template tables now raise ``UnsupportedFeatureError`` for presentation options
  that the data-only target route previously ignored. Repeated template blocks
  also reject formulas and workbook structures that OpenPyXL cannot shift safely,
  instead of producing a silently corrupted workbook.


## [0.2.1] - 2026-09-02

### Features

- Allow automatic spreadsheet column widths to declare backend-neutral minimum and maximum bounds with `AutoWidth`.
- Allow row expressions to apply a Python value transformation with `.transform(function)` without hiding field or column dependencies inside a lambda.


## [0.2.1] - 2026-09-01

### Features

- Support installing and running Caxton on Python 3.10, including the public
  spreadsheet API, bundled XLSX backends, and testing helpers.


## [0.2.0] - 2026-09-01

### Breaking changes

- Spreadsheet tables now use the single keyword-only
  `table(source=..., columns=(...))` form. Typed columns use flat keyword-only
  factories such as `text(source="name", title="Name")`; the positional table
  form, source inference from `id`, and the `column.<type>` namespace have been
  removed. A string source supplies the semantic id when it is omitted, while
  expressions and formulas require an explicit id.

  Matrix dimensions also accept raw field names, and all declarations continue to
  produce immutable semantic nodes before compilation. ([#24](https://github.com/dzhalaevd/caxton/issues/24))

### Bug fixes

- Reject foreign objects in spreadsheet semantic graphs at construction time, and include column grouping intent in semantic comparison diagnostics.
- Report output-target failures as structured `OutputError` exceptions, preserve
  their I/O causes, and keep all error context as immutable snapshots.


## [0.1.2] - 2026-08-31

### Bug fixes

- Detect direct, indirect, and cross-sheet reference cycles during structural
  validation and report their complete semantic path through
  `CyclicReferenceError`. ([#20](https://github.com/dzhalaevd/caxton/issues/20))


## [0.1.0] - 2026-08-19

### Features

- Add public spreadsheet API with data-source ingestion, semantic types, references, validation, styles, formulas,
  streaming, and direct XLSX output ([#2](https://github.com/dzhalaevd/caxton/issues/2))
- Add declarative spreadsheet blocks: `title`, `spacer`, `image`, `chart` and the `stack` flow container.
  A sheet now places its blocks sequentially without manual `start_row` arithmetic, explicit `anchor` stays
  available as a layout escape hatch, overlapping placed blocks are rejected during validation, and the
  XlsxWriter backend lowers titles, images and the supported chart
  kinds. ([#3](https://github.com/dzhalaevd/caxton/issues/3))
- Add grouped reports and pivot matrices with flexible aggregates, typed keys,
  and single-pass buffering. Enforce XLSX bounds and avoid dense sparse
  materialization. ([#4](https://github.com/dzhalaevd/caxton/issues/4))
- Add a format-independent template specification and a dedicated XLSX template
  route with named-range table targets, styled block repetition, OpenPyXL hooks,
  and pivot package post-processing. ([#5](https://github.com/dzhalaevd/caxton/issues/5))

### Documentation

- Added a MkDocs documentation site with a Material theme and a mkdocstrings API
  reference, a `docs` dependency group, `docs` and `docs-serve` tox environments, and a
  GitHub Pages deployment workflow that builds with `--strict`. ([#6](https://github.com/dzhalaevd/caxton/issues/6))
