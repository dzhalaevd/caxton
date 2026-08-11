from __future__ import annotations

import dataclasses
import os
import tempfile
from io import BytesIO
from pathlib import Path

from formata.core.errors import RenderError
from formata.core.protocols import (
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
        except BaseException:
            self.discard_staged(staged)
            raise

    def create_staging_path(self) -> Path:
        """Reserve a sibling path for direct backend output.

        Returns:
            A temporary path owned by this sink until commit or discard.
        """
        with tempfile.NamedTemporaryFile(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            return Path(stream.name)

    def commit_staged(self, staged: Path) -> int:
        """Atomically replace the target with a completed staged artifact.

        Returns:
            The committed artifact size in bytes.
        """
        bytes_written = staged.stat().st_size
        staged.replace(self.path)
        return bytes_written

    def discard_staged(self, staged: Path) -> None:
        """Remove an incomplete staged artifact if it still exists."""
        staged.unlink(missing_ok=True)


@dataclasses.dataclass(frozen=True, slots=True)
class BufferSink:
    """Adapt a writable binary file-like object to OutputSink."""

    buffer: BinaryWritable

    def write(self, data: bytes) -> int:
        return _write_all(self.buffer, data)

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
class CapturingSink:
    """Capture exactly the bytes accepted by another output sink."""

    sink: OutputSink
    _buffer: bytearray = dataclasses.field(default_factory=bytearray)

    def write(self, data: bytes) -> int:
        written = _write_all(self.sink, data)
        self._buffer.extend(data)
        return written

    def getvalue(self) -> bytes:
        """Return the captured artifact bytes."""
        return bytes(self._buffer)


def coerce_output_sink(target: OutputTarget) -> tuple[OutputSink, str | None]:
    """Normalize a path or binary buffer into an output sink.

    Returns:
        The sink and an optional human-readable target label.

    Raises:
        TypeError: If the target is neither a path nor a binary buffer.
    """
    if isinstance(target, (str, os.PathLike)):
        path = Path(target)
        return FileSink(path), str(path)
    if isinstance(target, BinaryWritable):
        return BufferSink(target), None
    message = f"Unsupported output target: {type(target).__name__}"
    raise TypeError(message)


def _write_all(target: BinaryWritable | OutputSink, data: bytes) -> int:
    total = 0
    while total < len(data):
        remaining = data[total:]
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
            raise RenderError(
                message,
                context={"remaining": len(remaining), "written": written},
            )
        if written == 0:
            message = "Output target did not accept the remaining artifact bytes"
            raise RenderError(message, context={"remaining": len(remaining)})
        total += written
    return total


__all__ = (
    "BufferSink",
    "CapturingSink",
    "FileSink",
    "MemorySink",
    "coerce_output_sink",
)
