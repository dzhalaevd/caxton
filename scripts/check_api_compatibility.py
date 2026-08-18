import os
import shutil
import subprocess  # noqa: S404
import sys


def latest_release_tag() -> str | None:
    """Return the newest version-like release tag, when one exists."""
    git_executable = shutil.which("git") or "git"
    completed = subprocess.run(  # noqa: S603
        [
            git_executable,
            "tag",
            "--list",
            "v[0-9]*",
            "--sort=-version:refname",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return next(iter(completed.stdout.splitlines()), None)


def main() -> int:
    """Check public API compatibility against an explicit or tagged baseline.

    Returns:
        Process exit status.
    """
    baseline = os.environ.get("API_BASELINE") or latest_release_tag()
    if baseline is None:
        sys.stdout.write("Griffe: no v* release tag found; API check skipped\n")
        return 0

    griffe_executable = shutil.which("griffe") or "griffe"
    completed = subprocess.run(  # noqa: S603
        [
            griffe_executable,
            "check",
            "--search",
            "src",
            "--format",
            "verbose",
            "--against",
            baseline,
            "caxton",
        ],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
