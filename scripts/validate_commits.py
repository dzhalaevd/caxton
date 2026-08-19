import argparse
import re
import shutil
import subprocess  # noqa: S404
import sys
from collections.abc import Sequence
from pathlib import Path

ALLOWED_TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)
TYPE_PATTERN = "|".join(ALLOWED_TYPES)
SUBJECT_PATTERN = re.compile(
    rf"^(?:{TYPE_PATTERN})(?:\([a-z0-9_.-]+(?:/[a-z0-9_.-]+)*\))?!?: \S.*$",
)


def is_conventional_subject(subject: str) -> bool:
    """Return whether a subject follows the Conventional Commits header."""
    return SUBJECT_PATTERN.fullmatch(subject) is not None


def commit_subjects(base: str, head: str) -> tuple[tuple[str, str], ...]:
    """Return non-merge commit identifiers and subjects in a Git range."""
    git_executable = shutil.which("git") or "git"
    completed = subprocess.run(  # noqa: S603
        [
            git_executable,
            "log",
            "--no-merges",
            "--format=%H%x00%s",
            f"{base}..{head}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    commits = []
    for line in completed.stdout.splitlines():
        identifier, subject = line.split("\0", maxsplit=1)
        commits.append((identifier, subject))
    return tuple(commits)


def validation_errors(
    commits: Sequence[tuple[str, str]],
    pull_request_title: str,
) -> tuple[str, ...]:
    """Return focused errors for non-conventional subjects and PR title."""
    errors = []
    if not is_conventional_subject(pull_request_title):
        errors.append(f"PR title: {pull_request_title!r}")
    errors.extend(
        f"commit {identifier[:12]}: {subject!r}"
        for identifier, subject in commits
        if not is_conventional_subject(subject)
    )
    return tuple(errors)


def message_file_errors(message_file: Path) -> tuple[str, ...]:
    """Return an error when a commit message subject is not conventional."""
    message = message_file.read_text(encoding="utf-8")
    subject = message.splitlines()[0] if message else ""
    if is_conventional_subject(subject):
        return ()
    return (f"commit message: {subject!r}",)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed validator arguments.
    """
    parser = argparse.ArgumentParser(
        description="Validate commits against Conventional Commits.",
    )
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--title")
    parser.add_argument("--message-file", type=Path)
    return parser.parse_args()


def main() -> int:
    """Validate the selected Git range and report actionable failures.

    Returns:
        Process exit status.
    """
    arguments = parse_arguments()
    if arguments.message_file is not None:
        errors = message_file_errors(arguments.message_file)
        validated_description = "commit message"
    elif all((arguments.base, arguments.head, arguments.title)):
        try:
            commits = commit_subjects(arguments.base, arguments.head)
        except subprocess.CalledProcessError as subprocess_error:
            sys.stderr.write(f"failed to inspect commits: {subprocess_error}\n")
            return 1
        errors = validation_errors(commits, arguments.title)
        validated_description = f"{len(commits)} commit subject(s) and the PR title"
    else:
        sys.stderr.write(
            "provide --message-file or all of --base, --head, and --title\n",
        )
        return 2

    if errors:
        allowed_types = ", ".join(ALLOWED_TYPES)
        sys.stderr.write(
            "Conventional Commits validation failed. Expected "
            "<type>[optional scope][!]: <description>.\n"
            f"Allowed types: {allowed_types}.\n",
        )
        for validation_error in errors:
            sys.stderr.write(f"- {validation_error}\n")
        return 1

    sys.stdout.write(f"validated {validated_description}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
