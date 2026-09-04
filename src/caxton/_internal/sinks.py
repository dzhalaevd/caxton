from __future__ import annotations

import contextlib
import dataclasses
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import NoReturn

from caxton.core.errors import CaxtonTypeError, OutputError
from caxton.core.protocols import (
    BinarySeekable,
    BinaryWritable,
    OutputSink,
    OutputTarget,
)


@dataclasses.dataclass(slots=True)
class MemorySink:
    """Collect rendered bytes for the public render operation."""

    _buffer: BytesIO = dataclasses.field(default_factory=BytesIO)

    def write(self, data: bytes) -> int:
        return self._buffer.write(data)

    @property
    def buffer(self) -> BytesIO:
        """The seekable buffer used by direct renderers."""
        return self._buffer

    def getvalue(self) -> bytes:
        """Return the collected artifact bytes."""
        return self._buffer.getvalue()


@dataclasses.dataclass(frozen=True, slots=True)
class FileSink:
    """Atomically commit one completed binary artifact to a path."""

    path: Path

    def write(self, data: bytes) -> int:
        staged = self.create_staging_path()
        try:
            with staged.open("wb") as stream:
                _write_all(stream, data)
            return self.commit_staged(staged)
        except OSError as error:
            with contextlib.suppress(OSError):
                self.discard_staged(staged)
            _raise_output_error(
                "Could not write the output artifact",
                error=error,
                operation="write",
                target=str(self.path),
            )
        except BaseException:
            self.discard_staged(staged)
            raise

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
            _raise_output_error(
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
            _raise_output_error(
                "Could not commit the output artifact",
                error=error,
                operation="commit",
                target=str(self.path),
            )
        return bytes_written

    def discard_staged(self, staged: Path) -> None:
        """Remove an incomplete staged artifact if it still exists."""
        staged.unlink(missing_ok=True)


@dataclasses.dataclass(frozen=True, slots=True)
class BufferSink:
    """Adapt a writable binary file-like object to OutputSink."""

    buffer: BinaryWritable

    def write(self, data: bytes) -> int:
        try:
            return _write_all(self.buffer, data)
        except (OSError, ValueError) as error:
            _raise_output_error(
                "Could not write the output artifact",
                error=error,
                operation="write",
                target_type=type(self.buffer).__name__,
            )

    def replace(self, data: bytes) -> int:
        """Overwrite a seekable target, or deliver to a forward-only stream.

        Returns:
            The number of delivered bytes.
        """
        try:
            written = self._replace(data)
        except (OSError, ValueError) as error:
            _raise_output_error(
                "Could not write the output artifact",
                error=error,
                operation="write",
                target_type=type(self.buffer).__name__,
            )
        return written

    def _replace(self, data: bytes) -> int:
        seekable = self.seekable_buffer
        truncate = getattr(self.buffer, "truncate", None)
        if seekable is None or not callable(truncate):
            return _write_all(self.buffer, data)
        seekable.seek(0)
        written = _write_all(self.buffer, data)
        truncate()
        seekable.flush()
        return written

    @property
    def seekable_buffer(self) -> BinarySeekable | None:
        """A direct target when the wrapped stream is seekable."""
        if isinstance(self.buffer, BinarySeekable):
            return self.buffer
        return None

    def getvalue(self) -> bytes | None:
        """Read an optional in-memory snapshot without changing position.

        Returns:
            Bytes exposed by an in-memory buffer, when available.
        """
        getvalue = getattr(self.buffer, "getvalue", None)
        if getvalue is None or not callable(getvalue):
            return None
        value = getvalue()
        return bytes(value) if isinstance(value, (bytes, bytearray)) else None


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
                return _write_all(stream, data)
        except OSError as error:
            _raise_output_error(
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


@dataclasses.dataclass(slots=True)
class BufferTransactionSink:
    """Defer delivery to an external buffer until rendering succeeds."""

    sink: BufferSink
    _buffer: BytesIO = dataclasses.field(default_factory=BytesIO)

    def write(self, data: bytes) -> int:
        return self._buffer.write(data)

    @property
    def buffer(self) -> BytesIO:
        """Invocation-owned buffer used for direct backend output."""
        return self._buffer

    def commit(self) -> int:
        """Deliver the completed artifact with overwrite semantics when possible.

        Returns:
            The number of delivered bytes.
        """
        return self.sink.replace(self._buffer.getvalue())

    def abort(self) -> None:
        """Drop staged bytes without touching the external target."""
        self._buffer = BytesIO()

    def getvalue(self) -> bytes:
        """Return the completed staged artifact."""
        return self._buffer.getvalue()


def coerce_output_sink(target: OutputTarget) -> tuple[OutputSink, str | None]:
    """Normalize a path or binary buffer into an output sink.

    Returns:
        The sink and an optional human-readable target label.

    Raises:
        CaxtonTypeError: If the target is neither a path nor a binary buffer.
    """
    if isinstance(target, (str, os.PathLike)):
        path = Path(target)
        return FileSink(path), str(path)
    if isinstance(target, BinaryWritable):
        return BufferSink(target), None
    message = f"Unsupported output target: {type(target).__name__}"
    raise CaxtonTypeError(
        message,
        context={"target_type": type(target).__name__},
    )


def _raise_output_error(
    message: str,
    *,
    error: OSError | ValueError,
    operation: str,
    target: str | None = None,
    target_type: str | None = None,
) -> NoReturn:
    context = {
        "exception_type": type(error).__name__,
        "operation": operation,
    }
    if target is not None:
        context["target"] = target
    if target_type is not None:
        context["target_type"] = target_type
    raise OutputError(message, context=context) from error


def _write_all(target: BinaryWritable | OutputSink, data: bytes) -> int:
    total = 0
    maximum_chunk_size = min(len(data), 64 * 1024)
    chunk_size = maximum_chunk_size
    while total < len(data):
        remaining = data[total : total + chunk_size]
        written = target.write(remaining)
        if written is None:
            written = len(remaining)
        if (
            isinstance(written, bool)
            or not isinstance(written, int)
            or written < 0
            or written > len(remaining)
        ):
            message = "Output target returned an invalid write count"
            raise OutputError(
                message,
                context={"remaining": len(remaining), "written": written},
            )
        if written == 0:
            message = "Output target did not accept the remaining artifact bytes"
            raise OutputError(message, context={"remaining": len(remaining)})
        total += written
        if written < len(remaining):
            chunk_size = max(written * 2, 1)
        else:
            chunk_size = maximum_chunk_size
    return total


__all__ = (
    "BufferSink",
    "BufferTransactionSink",
    "FileSink",
    "FileTransactionSink",
    "MemorySink",
    "coerce_output_sink",
)
