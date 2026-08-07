# Changelog fragments

Towncrier reads release notes from this directory and renders them into
`CHANGELOG.md`.

Create one fragment per change:

```text
<issue-id>.<type>.md
```

Supported types are `breaking`, `feature`, `bugfix`, `doc`, `generation` and
`ci`. For example: `123.feature.md`.

Create a fragment with Towncrier:

```bash
hatch run towncrier create --content "Describe the user-visible change." 123.feature.md
```

Use a GitHub issue or pull request number when one exists. Otherwise, prefix a
short unique identifier with `+`, for example `+typing.bugfix.md`.

Preview the next changelog entry without modifying files:

```bash
hatch run changelog-draft
```

Build the changelog during a release, using the version from
`src/formata/__version__.py`:

```bash
hatch run changelog-build "$(hatch version)"
```
