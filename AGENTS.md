# Repository guide for agents

Formata is a typed, declarative Python library for building documents. The
current production path is spreadsheet → XLSX; other families and advanced XLSX
features may be specified but not implemented.

## Read before changing

- **Architecture:** read [`ARCHITECTURE.md`](ARCHITECTURE.md) before changing
  public models, package boundaries, compilation, rendering, data ingestion,
  testing contracts, or extension points. Keep it as the single architectural
  source of truth.
- **Feature scope and examples:** read
  [`example/README.md`](example/README.md) before implementing or documenting a
  scenario. It maps working and deferred use cases to end-to-end flows; related
  cases belong in one flow, not one file each.

## Architecture guardrails

- Public factories create immutable semantic nodes. Generative methods return a
  new node; nested public collections are normalized to read-only values.
- Semantic models contain intent only. Coordinates, resolved layout, execution
  state, caches, workbook objects, XML, and engine-native values stay outside
  the model.
- Preserve dependency direction: `api → core/_internal`, `_internal → core`,
  and `testing → core/_internal`. `core` never imports `api`, `_internal`,
  testing, OpenPyXL, or XlsxWriter; `_internal` never imports `api`.
- Public operations return public types. Engine objects and mutable compiler
  state remain implementation details.
- A document family owns its model, validation, compiler, IR, and testing view.
  Add family-specific behavior to that family instead of a universal document
  or IR.
- Keep column `id`, `source`, and display `title` distinct. Expressions and
  selectors resolve semantic ids, not physical coordinates or titles.
- Coercion and structural validation never consume row data. Preserve
  `REITERABLE`/`ONE_SHOT`/`UNKNOWN` behavior and reject hidden extra passes.
- Resolve requirements, workbook operation, capabilities, and renderer
  compatibility before opening or writing the target.
- Raise stable `FormataError` subclasses with semantic context and preserve
  implementation exceptions through chaining.

## Implementation workflow

1. Inspect the affected public contract, tests, and current git status. Preserve
   unrelated working-tree and index changes.
2. Write or update a focused test that observes the behavior at the narrowest
   meaningful boundary: semantic model, layout, renderer, or artifact.
3. Implement the smallest coherent change while preserving the architecture
   guardrails above.
4. Run focused tests first, then the checks proportional to the change.
5. Review the final diff for accidental API exposure, eager data consumption,
   engine leakage, generated artifacts, and stale documentation.

Completion means the new behavior is tested, relevant contracts and examples
agree with it, required checks pass, and no unrelated files were rewritten.

## Commands

The repository uses the checked-in `.venv` tools through `Makefile` targets:

```bash
make test                         # full pytest suite
make lint                         # Ruff format/check + WPS
make typecheck                    # strict mypy
make dependencies                 # deptry
make imports                      # import boundary contracts
make coverage                     # tests with coverage threshold
make validate                     # complete local validation
```

During iteration, run focused tests directly:

```bash
.venv/bin/pytest tests/test_rendering.py -q
.venv/bin/pytest tests/test_streaming.py -q
```

For a public API change, also run:

```bash
make api-compatibility API_BASELINE=<tag-or-branch>
```

Use `uv sync` only when the environment must be created or refreshed. The
backend example has an independent environment under `example/backend`.

## Tests and examples

- Test public behavior through `formata`/`formata.api`; import `_internal` only
  for an explicitly internal contract test.
- Add typing fixtures under `tests/typing` when changing protocols or public
  generic signatures.
- Use `formata.testing` semantic and layout views for structural assertions;
  inspect the finished artifact when renderer output matters.
- One-shot tests must prove when the source is first consumed and that a second
  pass raises the focused error instead of silently returning no rows.
- Cover both bundled XLSX adapters only when behavior is intended to be shared;
  keep engine-specific expectations in focused backend tests.
- Every example Python file starts with a short module docstring. Working API is
  executable and self-checking; deferred API is described by a docstring rather
  than mocked with fictional imports.
- Generated example output belongs in an ignored `output/` directory. Keep only
  intentional input assets, such as the template workbook, in version control.

## Documentation and changelog

- Update `ARCHITECTURE.md` only when an architectural contract changes; update
  the example map when implementation status changes.
- Keep `README.md` quick-start code executable against the current public API.
- Add one Towncrier fragment for a user-visible change using
  `changelog.d/<issue-or-+slug>.<type>.md`. Supported types and commands are in
  [`changelog.d/README.md`](changelog.d/README.md).
- Edit fragments, not generated release notes in `CHANGELOG.md`.
