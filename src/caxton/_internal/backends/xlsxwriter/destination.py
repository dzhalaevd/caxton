from __future__ import annotations

import dataclasses
from io import BytesIO

from caxton._internal.sinks import (
    BufferTransactionSink,
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

    @classmethod
    def for_sink(cls, sink: OutputSink) -> WorkbookDestination:  # noqa: WPS212
        """Use the sink directly when possible, otherwise stage the output.

        Returns:
            A destination owning any required staging resource.
        """
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
        buffer = BytesIO()
        return cls(target=buffer, sink=sink, staged_buffer=buffer)

    def finish(self) -> int:
        """Commit the finished workbook and return its written size.

        Returns:
            The number of bytes delivered to the sink.
        """
        if self.staged_buffer is not None:
            return self.sink.write(self.staged_buffer.getvalue())
        if isinstance(self.sink, FileTransactionSink):
            return self.sink.staging_path.stat().st_size
        return self._direct_size()

    def _direct_size(self) -> int:
        if isinstance(self.sink, (MemorySink, BufferTransactionSink)):
            return len(self.sink.getvalue()) - self.start_position
        message = "Direct XLSX destination did not expose its written size"
        raise RuntimeError(message)


__all__ = ("WorkbookDestination",)
