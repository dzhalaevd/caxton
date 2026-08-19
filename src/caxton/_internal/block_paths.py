"""Walk declared spreadsheet blocks with stable semantic diagnostic paths."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from caxton.core.models import SpreadsheetBlock, Stack


def iter_blocks_with_paths(
    blocks: Sequence[SpreadsheetBlock],
    *,
    prefix: str = "block",
    recursive: bool = True,
) -> Iterator[tuple[SpreadsheetBlock, str]]:
    """Yield declared blocks and their paths in the nested Stack tree."""
    for index, block in enumerate(blocks):
        path = f"{prefix}[{index}]"
        yield block, path
        if recursive and isinstance(block, Stack):
            yield from iter_blocks_with_paths(block.items, prefix=f"{path}.item")


__all__ = ("iter_blocks_with_paths",)
