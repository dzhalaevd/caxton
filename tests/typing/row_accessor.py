from __future__ import annotations

from collections.abc import Mapping

from formata.core.protocols import RowAccessor


class MappingAccessor:
    def __call__(self, row: Mapping[str, object], field: str) -> object:
        return row[field]


custom_row_accessor: RowAccessor[Mapping[str, object]] = MappingAccessor()
