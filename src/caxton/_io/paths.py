from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

from caxton._io.delivery import write_all
from caxton._io.errors import raise_output_error


@dataclasses.dataclass(frozen=True, slots=True)
class FileSink:
    """Manage transaction staging for one output path."""

    path: Path

    def create_staging_path(self) -> Path:
        """Reserve a sibling path for direct backend output.

        Returns:
            A temporary path owned by this sink until commit or discard.
        """
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                return Path(stream.name)
        except OSError as error:
            raise_output_error(
                "Could not create a staging file for the output target",
                error=error,
                operation="create_staging_file",
                target=str(self.path),
            )

    def commit_staged(self, staged: Path) -> int:
        """Atomically replace the target with a completed staged artifact.

        Returns:
            The committed artifact size in bytes.
        """
        try:
            bytes_written = staged.stat().st_size
            staged.replace(self.path)
        except OSError as error:
            raise_output_error(
                "Could not commit the output artifact",
                error=error,
                operation="commit",
                target=str(self.path),
            )
        return bytes_written

    @staticmethod
    def discard_staged(staged: Path) -> None:
        """Remove an incomplete staged artifact if it still exists."""
        staged.unlink(missing_ok=True)


@dataclasses.dataclass(slots=True)
class FileTransactionSink:
    """Accumulate one renderer invocation in a sibling staging file."""

    sink: FileSink
    _staged: Path | None = None

    @property
    def staging_path(self) -> Path:
        """Invocation-owned staging path, created lazily."""
        if self._staged is None:
            self._staged = self.sink.create_staging_path()
        return self._staged

    def write(self, data: bytes) -> int:
        try:
            with self.staging_path.open("ab") as stream:
                return write_all(stream, data)
        except OSError as error:
            raise_output_error(
                "Could not write the output artifact",
                error=error,
                operation="write",
                target=str(self.sink.path),
            )

    def commit(self) -> int:
        """Atomically publish every chunk written during the invocation.

        Returns:
            The committed artifact size.
        """
        return self.sink.commit_staged(self.staging_path)

    def abort(self) -> None:
        """Discard the invocation staging file, if one was created."""
        if self._staged is not None:
            self.sink.discard_staged(self._staged)


__all__ = ("FileSink", "FileTransactionSink")
