import argparse
import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_RE = re.compile(
    r'^__version__[ \t]*=[ \t]*"(?P<version>\d+\.\d+\.\d+)"[ \t]*$',
    re.MULTILINE,
)
DEFAULT_VERSION_FILE = Path("src/formata/__version__.py")


def bump_version(version: str, part: str) -> str:
    """Increment one part of a semantic version.

    Args:
        version: Semantic version in ``MAJOR.MINOR.PATCH`` format.
        part: Version part to increment.

    Returns:
        Incremented semantic version.

    Raises:
        ValueError: If the version or part is unsupported.
    """
    match = SEMVER_RE.fullmatch(version)
    if match is None:
        message = f"Unsupported version format: {version}. Expected MAJOR.MINOR.PATCH."
        raise ValueError(message)

    major, minor, patch = map(int, match.groups())
    if part == "major":
        bumped = (major + 1, 0, 0)
    elif part == "minor":
        bumped = (major, minor + 1, 0)
    elif part == "patch":
        bumped = (major, minor, patch + 1)
    else:
        message = f"Unsupported version part: {part}"
        raise ValueError(message)
    return ".".join(map(str, bumped))


def read_version(path: Path) -> tuple[str, str]:
    """Return file content and the version found in it.

    Raises:
        ValueError: If the file does not contain a supported version declaration.
    """
    source_text = path.read_text(encoding="utf-8")
    match = VERSION_RE.search(source_text)
    if match is None:
        message = f"Could not find __version__ in {path}"
        raise ValueError(message)
    return source_text, match.group("version")


def update_version(path: Path, part: str) -> tuple[str, str]:
    """Increment and persist the selected version part.

    Returns:
        Previous and updated versions.
    """
    source_text, old_version = read_version(path)
    new_version = bump_version(old_version, part)
    replacement = f'__version__ = "{new_version}"'
    updated_text = VERSION_RE.sub(replacement, source_text, count=1)
    path.write_text(updated_text, encoding="utf-8")
    return old_version, new_version


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed command-line namespace.
    """
    parser = argparse.ArgumentParser(description="Bump the package version.")
    parser.add_argument("part", choices=("major", "minor", "patch"))
    parser.add_argument("--file", default=DEFAULT_VERSION_FILE, type=Path)
    return parser.parse_args()


def main() -> int:
    """Run the version bump command.

    Returns:
        Process exit status.
    """
    arguments = parse_arguments()
    try:
        old_version, new_version = update_version(arguments.file, arguments.part)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(f"Bumped version: {old_version} -> {new_version}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
