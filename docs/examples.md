# Examples

The repository ships runnable example projects under
[`example/`](https://github.com/dzhalaevd/caxton/tree/main/example). Each one is a
self-verifying script: it builds a document, asserts what the compiler and the
renderer produced, and writes its artifact into an ignored `output/` directory.

Run one with the repository environment:

```bash
uv run python example/basic/report.py
```

## `basic` — multi-sheet report, end to end

Composes columns dynamically, derives a `profit` column with `ref()`, and then
walks every public boundary in turn: `validate()`, `inspect_spec()`,
`inspect_layout()` with a bounded row scope, `render()` into memory,
`inspect_artifact()`, and finally a buffer write.

Start here if you want one file that shows the whole surface.

## `reusable` — one factory, many documents

Calls the same report factory with different row sets and different metadata,
producing two artifacts without copying or mutating a shared model. This is the
current answer to "reusable templates" — bind-time placeholders are deferred.

## `advanced` — formulas, grouping, matrices

The widest feature slice:

- live formulas with mixed absolute/relative axes (`col("base_price").absolute(row=False)`);
- cross-sheet and structured references (`sheet_ref(...)`, `table_ref(...)`);
- a totals footer, conditional rules, autofilter, freeze panes, auto width;
- a hierarchically grouped table with a filtered Python aggregate and a default;
- a matrix with dynamic axes;
- a `StyleSheet` plus a `CorporateTheme`.

It then asserts the rendered formulas and merge ranges in the finished workbook.

## `dashboard` — block layout

A single worksheet built from `title()`, `spacer()`, a table, and a `stack()`
containing a chart bound with `table_ref()` and an embedded image. No manual row
arithmetic anywhere; the assertions show exactly which anchors the layout pass
chose.

## `template` — filling an existing workbook

Loads a bundled XLSX template, writes rows into its `report_data` named range
with `into=ref(...)`, and attaches an OpenPyXL hook to set the print area. It
asserts both the populated values and that the source template file is
byte-identical afterwards.

## `backend` — a web service

A small FastAPI application with its own environment under `example/backend`. It
reads dataclass DTOs out of SQLite, uses `path()` for a nested owner value and
`ref()` for derived columns, and returns `render(...).data` straight into an HTTP
response with the XLSX media type — no temporary file involved.

```bash
cd example/backend
uv sync
uv run uvicorn app:app --reload
```
