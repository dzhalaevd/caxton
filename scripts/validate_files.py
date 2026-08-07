"""Validate Towncrier fragments listed in a changed-files manifest."""

import re
import sys
from pathlib import Path

CHANGELOG_PATTERN = re.compile(
    r"^changelog\.d/(?:\d+|\+[a-z0-9][a-z0-9_-]*)\."
    r"(?:breaking|feature|bugfix|doc|generation|ci)\.md$",
)
IGNORED_FILES = ("README.md",)


def iter_fragments(changed_files: Path) -> tuple[str, ...]:
    """Return changelog paths from a changed-files manifest."""
    lines = changed_files.read_text(encoding="utf-8").splitlines()
    return tuple(
        path
        for changed_path in lines
        if (path := changed_path.strip()).startswith("changelog.d/")
        and Path(path).name not in IGNORED_FILES
    )


def validate_fragment(path: str, project_root: Path) -> None:
    """Validate the name and content of one fragment.

    Raises:
        ValueError: If the fragment name or content is invalid.
    """
    if CHANGELOG_PATTERN.fullmatch(path) is None:
        message = f"invalid changelog fragment {path}: invalid filename"
        raise ValueError(message)

    fragment = project_root / path
    if not fragment.is_file():
        message = f"invalid changelog fragment {path}: file does not exist"
        raise ValueError(message)
    if not fragment.read_text(encoding="utf-8").strip():
        message = f"invalid changelog fragment {path}: fragment is empty"
        raise ValueError(message)


def validate_files(changed_files: Path, project_root: Path) -> None:
    """Validate that the manifest contains at least one valid fragment.

    Raises:
        ValueError: If the manifest has no valid changelog fragments.
    """
    fragments = iter_fragments(changed_files)
    if not fragments:
        message = "no changelog fragment added in this change"
        raise ValueError(message)
    for fragment in fragments:
        validate_fragment(fragment, project_root)


def main() -> int:
    """Run the changelog validation command.

    Returns:
        Process exit status.
    """
    if len(sys.argv) != 2:
        sys.stderr.write("usage: validate_files.py <changed-files.txt>\n")
        return 1
    try:
        validate_files(Path(sys.argv[1]), Path.cwd())
    except (OSError, ValueError) as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write("changelog validation passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
