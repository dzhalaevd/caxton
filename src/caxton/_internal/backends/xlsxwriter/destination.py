"""Adapt output sinks into destinations accepted by XlsxWriter."""

from __future__ import annotations

import dataclasses
from io import BytesIO
from pathlib import Path

from caxton._internal.sinks import (
    BufferSink,
    BufferTransactionSink,
    FileSink,
    FileTransactionSink,
    MemorySink,
)
from caxton.core.protocols import OutputSink


@dataclasses.dataclass(slots=True)
class WorkbookDestination:
    """Adapt a Caxton output sink to an XlsxWriter workbook target."""

    target: object
    sink: OutputSink
    start_position: int = 0
    staged_buffer: BytesIO | None = None
    staged_file: Path | None = None

    @classmethod
    def for_sink(cls, sink: OutputSink) -> WorkbookDestination:  # noqa: WPS212
        """Create the most direct destination supported by the sink.

        Returns:
            A destination owning any required staging resource.
        """
        if isinstance(sink, FileSink):
            return cls._for_file(sink)
        if isinstance(sink, FileTransactionSink):
            return cls(target=str(sink.staging_path), sink=sink)
        if isinstance(sink, BufferTransactionSink):
            return cls(
                target=sink.buffer,
                sink=sink,
                start_position=sink.buffer.tell(),
            )
        if isinstance(sink, MemorySink):
            return cls(
                target=sink.buffer,
                sink=sink,
                start_position=sink.buffer.tell(),
            )
        if isinstance(sink, BufferSink) and sink.seekable_buffer is not None:
            target = sink.seekable_buffer
            return cls(target=target, sink=sink, start_position=target.tell())
        buffer = BytesIO()
        return cls(target=buffer, sink=sink, staged_buffer=buffer)

    @classmethod
    def _for_file(cls, sink: FileSink) -> WorkbookDestination:
        staged_file = sink.create_staging_path()
        return cls(
            target=str(staged_file),
            sink=sink,
            staged_file=staged_file,
        )

    def finish(self) -> int:
        """Commit the finished workbook and return its written size.

        Returns:
            The number of bytes delivered to the sink.
        """
        if self.staged_file is not None and isinstance(self.sink, FileSink):
            return self.sink.commit_staged(self.staged_file)
        if self.staged_buffer is not None:
            return self.sink.write(self.staged_buffer.getvalue())
        if isinstance(self.sink, FileTransactionSink):
            return self.sink.staging_path.stat().st_size
        return self._direct_size()

    def _direct_size(self) -> int:
        if isinstance(self.sink, (MemorySink, BufferTransactionSink)):
            return len(self.sink.getvalue()) - self.start_position
        if isinstance(self.sink, BufferSink):
            target = self.sink.seekable_buffer
            if target is not None:
                return target.tell() - self.start_position
        message = "Direct XLSX destination did not expose its written size"
        raise RuntimeError(message)

    def abort(self) -> None:
        """Discard any uncommitted file staging owned by the destination."""
        if self.staged_file is not None and isinstance(self.sink, FileSink):
            self.sink.discard_staged(self.staged_file)


__all__ = ("WorkbookDestination",)
