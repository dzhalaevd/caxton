from __future__ import annotations

import os
from pathlib import Path

from caxton._io.buffers import BufferSink, BufferTransactionSink, MemorySink
from caxton._io.paths import FileSink, FileTransactionSink
from caxton.core.errors import CaxtonTypeError
from caxton.core.protocols import BinaryWritable, OutputTarget


def coerce_output_sink(
    target: OutputTarget,
) -> tuple[FileSink | BufferSink, str | None]:
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


__all__ = (
    "BufferSink",
    "BufferTransactionSink",
    "FileSink",
    "FileTransactionSink",
    "MemorySink",
    "coerce_output_sink",
)
