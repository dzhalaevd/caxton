# Contributing

Thanks for contributing to Caxton. This guide covers development and releases. If you get stuck, open a discussion.

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

Use the checked-in virtual environment:

```bash
.venv/bin/pytest -q
```

Run repository-level gates through tox, matching CI:

```bash
uv run --no-sync tox run -e py314        # tests on one interpreter
uv run --no-sync tox run -e pre-commit   # lint, typing, imports, hygiene
uv run --no-sync tox run -e build        # wheel and sdist validation
uv run --no-sync tox run -e docs         # strict documentation build
```

The full matrix is `py310`, `py311`, `py312`, `py313`, `py314`. CI also tests the built wheel and sdist on Linux, macOS
and Windows.

Two convenience targets exist:

```bash
make coverage
make benchmark
```

## Work on the documentation

```bash
uv run --no-sync tox run -e docs-serve    # live reload on http://127.0.0.1:8000
uv run --no-sync tox run -e docs          # strict build, as CI runs it
```

The site uses [MkDocs](https://www.mkdocs.org/) with
[Material](https://squidfunk.github.io/mkdocs-material/), and
[mkdocstrings](https://mkdocstrings.github.io/) generates the API reference from docstrings. The strict build fails on
broken internal links and unresolved references.

Published prose pages live in `docs/`, and their navigation is defined in `mkdocs.yml`. `ARCHITECTURE.md` is the
normative source for architecture, while `CHANGELOG.md` and the Towncrier fragments are the sources for release notes.
Edit those source files instead of duplicating their content in a guide.

## Architectural guardrails

- Public factories create **immutable** nodes; fluent methods return new ones.
- Semantic models hold intent only — no coordinates, resolved layout, caches or engine-native values.
- Dependency direction is defined in `ARCHITECTURE.md`: `api` and `testing` may use private implementation modules;
  `_pipeline` coordinates `_spreadsheet`, `_xlsx` and `_io`; `_xlsx` may use `_spreadsheet` and `_io`; `_spreadsheet`,
  `_source` and `_io` depend only on Core. Private modules never import `api` or `testing`.
- Column `id`, `source` and `title` stay distinct.
- Coercion and structural validation never consume rows; `REITERABLE` /
  `ONE_SHOT` / `UNKNOWN` behavior is preserved and hidden extra passes are rejected.
- Errors are stable `CaxtonError` subclasses with semantic context, chained to the original cause.
- Treat deferred capabilities as absent — a name in a design note does not reserve a public API.

`import-linter` contracts and the Griffe API compatibility check enforce some of these rules. Breaking one usually fails
the `pre-commit` tox environment.

## Workflow

1. Inspect the affected public contract and tests; preserve unrelated changes.
2. Add or update a focused test at the narrowest meaningful boundary — semantic model, layout, renderer or artifact.
3. Make the smallest coherent change.
4. Run focused tests, then checks proportional to the change.
5. Review the final diff for accidental API exposure, eager data consumption, engine leakage, generated artifacts and
   stale documentation.

## Release process

Caxton releases from `main`; there is no separate long-lived development branch.

The default cadence is a weekly release window, not a weekly obligation. Skip the release when there is no user-visible
change worth publishing. A fix for a bad release does not wait for the next window.

## Day-to-day development

Create a short branch from `main` and open the pull request against `main`. Use names such as
`feat/declarative-columns`, `fix/short-buffer-write` or
`docs/template-guide`; the prefix describes the work but does not determine the package version.

Add one Towncrier fragment for every user-visible change:

```text
changelog.d/<issue-or-+slug>.<type>.md
```

The supported types are `breaking`, `feature`, `bugfix`, `doc`, `generation`
and `ci`. Use the issue or pull request number when one exists. Otherwise use a short name prefixed with `+`:

```bash
hatch run towncrier create \
  --content "Preserve text written through a short-writing buffer." \
  123.bugfix.md
```

Write the fragment for a package user. State the behavior that changed and any action required during an upgrade.
Implementation notes belong in the pull request.

Do not change `src/caxton/__version__.py` or generate `CHANGELOG.md` in a feature pull request. Those changes are made
once, in the release pull request, so parallel work does not compete over a version number or generated file.

Delete the branch after it is merged. Caxton does not use `develop` or permanent release branches. A maintenance branch
becomes useful only when the project commits to supporting two release lines at the same time.

## Choose the version

Caxton uses three-part versions compatible with
[Semantic Versioning](https://semver.org/) and Python's
[PEP 440](https://packaging.python.org/en/latest/specifications/version-specifiers/). While the public API is below
`1.0`, the project follows a stricter convention than SemVer requires: a patch release must not break documented public
behavior.

| Change in the release                      | Before `1.0`                    | From `1.0` onward               |
|--------------------------------------------|---------------------------------|---------------------------------|
| Backward-incompatible public API change    | next minor, for example `0.3.0` | next major, for example `2.0.0` |
| Backward-compatible public feature         | next minor                      | next minor                      |
| Backward-compatible bug or performance fix | next patch                      | next patch                      |
| Documentation or CI only                   | no package release by default   | no package release by default   |

When a release contains several kinds of change, use the largest required bump. A breaking change needs a `breaking`
fragment even before `1.0`.

Pre-releases are reserved for changes that need feedback before ordinary users upgrade, such as a broad rewrite of the
public DSL. Use PEP 440 spelling such as
`0.4.0rc1`. The current version bump script handles final releases only; extend and test that tooling before publishing
a pre-release.

## Prepare the release pull request

Start from an up-to-date `main` and create a branch for the release:

```bash
git switch main
git pull --ff-only
git switch -c chore/release-v0.3.0
```

Inspect the pending notes before choosing the final version:

```bash
hatch run changelog-draft
```

Bump the appropriate component, then let Towncrier consume the fragments and write the new section at the top of
`CHANGELOG.md`:

```bash
hatch run bump-version minor
hatch run changelog-build "$(hatch version)"
```

Review the generated section. It should describe only shipped behavior, group entries under the right headings and call
out every incompatible change. Check that the version file and generated heading agree:

```bash
hatch version
git diff -- src/caxton/__version__.py CHANGELOG.md changelog.d
```

Run the repository gates before opening the pull request:

```bash
uv run --no-sync tox run -e py314
uv run --no-sync tox run -e pre-commit
uv run --no-sync tox run -e build
```

Documentation changes also require the strict documentation build:

```bash
uv run --no-sync tox run -e docs
```

Commit the release preparation, push the branch and open a pull request into
`main`:

```bash
git add src/caxton/__version__.py CHANGELOG.md changelog.d
git commit -m "chore(release): prepare v0.3.0"
git push -u origin chore/release-v0.3.0
```

Apply the `skip-changelog` label to this pull request: it consumes the pending fragments instead of adding another one.
Merge only after the full CI run passes. The release commit must reach `main` before the tag is created.

## Tag and publish

Update the local `main`, verify the version and create an annotated tag on the release commit:

```bash
git switch main
git pull --ff-only
test "$(hatch version)" = "0.3.0"
git tag -a v0.3.0 -m "Caxton 0.3.0"
git push origin v0.3.0
```

Pushing `v*` starts `.github/workflows/release.yml`. The workflow reruns the quality gates, then builds, verifies and
attests the wheel and source distribution. It creates the GitHub Release and dispatches the Trusted Publishing workflow
for PyPI.

The release is complete when all the following are true:

- the tag points to the intended commit on `main`;
- the GitHub Release is published with the wheel, source distribution and
  `SHA256SUMS`;
- the same version is available from PyPI;
- installing the published wheel succeeds in the CI package test.

## When publication fails

If a transient CI or publishing step fails, fix its external cause and rerun the failed workflow. Do not move a public
tag to another commit.

If the tagged source itself is wrong, merge the correction into `main` and make a new release. Published package
versions and tags are immutable; never delete and reuse their numbers. Use a patch release for a compatible correction.
Use the version table above if the correction changes public behavior.

## Reaching `1.0.0`

Release `1.0.0` when the documented public DSL is a compatibility commitment:
ordinary upgrades may add behavior or fix bugs, while incompatible changes need a major release. Before that tag,
document the supported public surface and the deprecation policy, and make sure the examples and compatibility checks
cover the API users are expected to depend on.
