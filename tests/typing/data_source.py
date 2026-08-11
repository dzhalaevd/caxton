from __future__ import annotations

import dataclasses
from collections.abc import Iterator

from formata.core.protocols import DataSource, DataSourceInfo, Repeatability


@dataclasses.dataclass(frozen=True)
class User:
    name: str


class UserSource:
    @property
    def repeatability(self) -> Repeatability:
        return Repeatability.REITERABLE

    @property
    def row_count(self) -> int:
        return 1

    def iter_rows(self) -> Iterator[User]:
        yield User("Ada")

    def get_value(self, row: User, field: str) -> object:
        return getattr(row, field)


custom_data_source: DataSource[User] = UserSource()
custom_data_source_info: DataSourceInfo = UserSource()
