# Changelog

<!-- towncrier release notes start -->

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
