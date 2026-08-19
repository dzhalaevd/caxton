# Repository guide for agents

Caxton is a typed, declarative Python library for building documents. The
current production path is spreadsheet → XLSX; other families and advanced XLSX
features may be specified but not implemented.

## Read before changing

- **Architecture:** read [`ARCHITECTURE.md`](ARCHITECTURE.md) before changing
  public models, package boundaries, compilation, rendering, data ingestion,
  testing contracts, or extension points. Keep it as the single architectural
  source of truth.
- **Feature scope:** use the delivered-profile and deliberate-deferrals sections
  of `ARCHITECTURE.md`. A proposed API in a design note or use case is not an
  implementation contract.
- **Examples:** inspect the nearest existing flow under `example/basic`,
  `example/reusable`, `example/advanced`, `example/dashboard`,
  `example/template`, or `example/backend`. Extend a coherent flow rather than
  adding one example file per small feature.

## Route changes to the owning boundary

- Public factories and immutable nodes belong in `caxton.api` and
  `caxton.core.models`; test construction, immutability, public exports, and
  typing together.
- Semantic values and presentation vocabulary belong in `caxton.core.types` and
  `caxton.core.formatting`; backend materialization stays in each renderer.
- Data coercion and row evaluation belong in the ingestion/evaluation layers;
  framework lifecycle and query planning remain application concerns.
- Requirement analysis, renderer resolution, compilation, and layout are
  separate internal stages. Do not move renderer selection into models or
  backend execution into the family compiler.
- Template inspection and XLSX-native escape hatches stay in the template/XLSX
  route. Package XML paths and native workbook objects never enter generic Core
  contracts.
- Testing features belong in `caxton.testing` and return immutable public views;
  parsers, IR traversal, and diff implementation remain internal.

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
- Raise stable `CaxtonError` subclasses with semantic context and preserve
  implementation exceptions through chaining.
- Do not introduce smart context-sensitive factories, universal document/IR
  types, framework adapters in Core, or global registries without first adding
  a concrete use case and updating `ARCHITECTURE.md`.
- Treat deferred capabilities as absent. Do not make a sketched name public just
  because it appears in a design note.

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

Use the checked-in `.venv` for focused iteration:

```bash
.venv/bin/pytest tests/test_rendering.py -q
.venv/bin/pytest tests/test_streaming.py -q
```

Run the repository-level gates through tox, matching CI:

```bash
uv run --no-sync tox run -e py314
uv run --no-sync tox run -e pre-commit
uv run --no-sync tox run -e build
```

The full Python matrix is `py311`, `py312`, `py313`, and `py314`; CI also tests
the built wheel and sdist across Linux, macOS, and Windows. `make coverage` and
`make benchmark` are the only convenience Make targets.

For a public API change, run the compatibility check against the intended
baseline (the newest `v*` tag is used when `API_BASELINE` is omitted):

```bash
API_BASELINE=<tag-or-branch> .venv/bin/python scripts/check_api_compatibility.py
```

Use `uv sync` only when the environment must be created or refreshed. The
backend example has an independent environment under `example/backend`.

## Tests and examples

- Test public behavior through `caxton`/`caxton.api`; import `_internal` only
  for an explicitly internal contract test.
- Add typing fixtures under `tests/types` when changing protocols or public
  generic signatures.
- Use `caxton.testing` semantic and layout views for structural assertions;
  inspect the finished artifact when renderer output matters.
- One-shot tests must prove when the source is first consumed and that a second
  pass raises the focused error instead of silently returning no rows.
- Grouped-table and matrix tests must prove exactly one source pass, stable
  grouping identity/order, aggregate error context, and placement based on the
  prepared output shape.
- Cover both bundled XLSX adapters only when behavior is intended to be shared;
  keep engine-specific expectations in focused backend tests.
- For sink/output changes, verify failure atomicity for paths, complete delivery
  for short-writing buffers, and that capability/template failures happen before
  the target is touched.
- For template or post-processing behavior, test through a minimal intentional
  binary fixture and inspect the completed artifact; do not assert public
  behavior through OpenPyXL objects or package XML unless the test is explicitly
  backend-internal.
- Generated example output belongs in an ignored `output/` directory. Keep only
  intentional input assets, such as the template workbook, in version control.

## Documentation and changelog

- Update `ARCHITECTURE.md` when an architectural contract, delivered capability,
  or deliberate deferral changes. Keep workflow-only guidance in `AGENTS.md`.
- Keep `README.md` quick-start code executable against the current public API.
- Add one Towncrier fragment for a user-visible change using
  `changelog.d/<issue-or-+slug>.<type>.md`. Supported types and commands are in
  [`changelog.d/README.md`](changelog.d/README.md).
- Edit fragments, not generated release notes in `CHANGELOG.md`.
- PR titles and every non-merge commit must follow
  `<type>[optional scope][!]: <description>`. The accepted types are enforced by
  `scripts/validate_commits.py`; CI also requires a valid Towncrier fragment for
  non-Dependabot PRs.
