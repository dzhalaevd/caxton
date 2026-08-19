# Contributing

Thanks for considering a contribution. This page is the short version; the
normative documents in the repository are
[`ARCHITECTURE.md`](architecture.md) (what the contracts are) and `AGENTS.md`
(how to work in the repository).

## Set up

```bash
git clone https://github.com/dzhalaevd/caxton.git
cd caxton
uv sync
```

Install the git hooks once:

```bash
uv run pre-commit install
```

## Run the checks

Fast iteration uses the checked-in environment:

```bash
pytest .
```

Repository-level gates run through tox, exactly as CI does:

```bash
uv run --no-sync tox run -e py314        # tests on one interpreter
uv run --no-sync tox run -e pre-commit   # lint, typing, imports, hygiene
uv run --no-sync tox run -e build        # wheel and sdist validation
uv run --no-sync tox run -e docs         # strict documentation build
```

The full matrix is `py311`, `py312`, `py313`, `py314`; CI additionally tests the
built wheel and sdist on Linux, macOS and Windows.

Two convenience targets exist:

```bash
make coverage
make benchmark
```

For a public API change, check compatibility against the intended baseline (the
newest `v*` tag is used when `API_BASELINE` is omitted):

```bash
API_BASELINE=<tag-or-branch> python scripts/check_api_compatibility.py
```

## Work on the documentation

```bash
uv run --no-sync tox run -e docs-serve    # live reload on http://127.0.0.1:8000
uv run --no-sync tox run -e docs          # strict build, as CI runs it
```

The site is built with [MkDocs](https://www.mkdocs.org/) and
[Material](https://squidfunk.github.io/mkdocs-material/); the API reference is
generated from docstrings by
[mkdocstrings](https://mkdocstrings.github.io/). Because the build is strict, a
broken internal link or an unresolvable reference fails CI.

Prose pages live in `docs/`. `docs/architecture.md` and `docs/changelog.md`
include the repository files rather than duplicating them, so edit
`ARCHITECTURE.md` and the changelog fragments instead.

The internal engineering notes — `docs/README.md`, `docs/adr/` and
`docs/use_case/` — are excluded from the published site via `exclude_docs` in
`mkdocs.yml`. They stay in the repository for contributors; remove them from that
list if you decide to publish them.

## Architectural guardrails

A change is much easier to accept when it respects these:

- Public factories create **immutable** nodes; fluent methods return new ones.
- Semantic models hold intent only — no coordinates, resolved layout, caches or
  engine-native values.
- Dependency direction is `api → core/_internal`, `_internal → core`,
  `testing → core/_internal`. `core` never imports `api`, `_internal`, testing,
  OpenPyXL or XlsxWriter; `_internal` never imports `api`.
- Column `id`, `source` and `title` stay distinct.
- Coercion and structural validation never consume rows; `REITERABLE` /
  `ONE_SHOT` / `UNKNOWN` behaviour is preserved and hidden extra passes are
  rejected.
- Errors are stable `CaxtonError` subclasses with semantic context, chained to
  the original cause.
- Treat deferred capabilities as absent — a name in a design note does not
  reserve a public API.

These are enforced in part by `import-linter` contracts and by the Griffe API
compatibility check, so breaking one usually fails the `pre-commit` tox env.

## Workflow

1. Inspect the affected public contract and tests; preserve unrelated changes.
2. Add or update a focused test at the narrowest meaningful boundary — semantic
   model, layout, renderer or artifact.
3. Make the smallest coherent change.
4. Run focused tests, then checks proportional to the change.
5. Review the final diff for accidental API exposure, eager data consumption,
   engine leakage, generated artifacts and stale documentation.

## Changelog and commits

Every user-visible change needs one Towncrier fragment:

```text
changelog.d/<issue-or-+slug>.<type>.md
```

Types are `breaking`, `feature`, `bugfix`, `doc`, `generation` and `ci`. Edit
fragments, never the generated `CHANGELOG.md`.

PR titles and all non-merge commits follow Conventional Commits:

```text
<type>[optional scope][!]: <description>
```

CI validates both the commit format and the presence of a fragment.
