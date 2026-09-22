from __future__ import annotations

from caxton.core.errors import OutputError
from caxton.core.protocols import BinaryWritable, OutputSink


def write_all(target: BinaryWritable | OutputSink, data: bytes) -> int:
    """Deliver every byte, retrying valid short writes.

    Returns:
        The number of bytes delivered.

    Raises:
        OutputError: If the destination reports an invalid or zero write count.
    """
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
