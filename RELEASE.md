# Release process

Caxton releases from `main`. The repository has one long-lived development branch; feature, fix and maintenance branches
exist only long enough to merge a pull request.

The default cadence is a weekly release window, not a weekly obligation. Skip the release when there is no user-visible
change worth publishing. A fix for a bad release does not wait for the next window.

## Day-to-day development

Create a short branch from `main` and open the pull request back into `main`. Use names such as
`feat/declarative-columns`, `fix/short-buffer-write` or
`docs/template-guide`; the prefix describes the work but does not determine the package version.

Every user-visible change carries one Towncrier fragment:

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

Pushing `v*` starts `.github/workflows/release.yml`. The workflow runs the quality gates again, builds and verifies the
wheel and source distribution, attests them, creates the GitHub Release and dispatches the Trusted Publishing workflow
for PyPI.

The release is complete when all of the following are true:

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
