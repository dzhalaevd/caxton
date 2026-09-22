from __future__ import annotations

import dataclasses
from io import BytesIO

from caxton._io.delivery import write_all
from caxton._io.errors import raise_output_error
from caxton.core.protocols import BinarySeekable, BinaryWritable


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
class BufferSink:
    """Manage transaction delivery to a writable binary buffer."""

    buffer: BinaryWritable

    def replace(self, data: bytes) -> int:
        """Overwrite a seekable target, or deliver to a forward-only stream.

        Returns:
            The number of delivered bytes.
        """
        try:
            written = self._replace(data)
        except (OSError, ValueError) as error:
            raise_output_error(
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
            return write_all(self.buffer, data)
        seekable.seek(0)
        written = write_all(self.buffer, data)
        truncate()
        seekable.flush()
        return written

    @property
    def seekable_buffer(self) -> BinarySeekable | None:
        """A direct target when the wrapped stream is seekable."""
        if isinstance(self.buffer, BinarySeekable):
            return self.buffer
        return None


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


__all__ = ("BufferSink", "BufferTransactionSink", "MemorySink")
