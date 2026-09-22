from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Mapping

from typing_extensions import assert_type

from caxton import data_source
from caxton._source import coerce_data_source  # noqa: PLC2701
from caxton.core.protocols import DataSource


@dataclasses.dataclass(frozen=True)
class User:
    name: str


class UserSource:
    def iter_rows(self) -> Iterator[User]:
        yield User("Ada")

    def get_value(self, row: User, field: str) -> object:
        return getattr(row, field)


class MappingAccessor:
    def __call__(self, row: Mapping[str, str], field: str) -> object:
        return row[field]


def user_rows() -> Iterator[User]:
    yield User("Ada")


users: list[User] = [User("Ada")]
ready: DataSource[User] = UserSource()
mapping: dict[str, str] = {"name": "Ada"}

assert_type(coerce_data_source(users), DataSource[User])
assert_type(coerce_data_source(ready), DataSource[User])
assert_type(coerce_data_source(mapping), DataSource[dict[str, str]])
assert_type(coerce_data_source(User("Ada")), DataSource[User])
assert_type(coerce_data_source(user_rows()), DataSource[User])
assert_type(
    coerce_data_source([mapping], accessor=MappingAccessor()),
    DataSource[dict[str, str]],
)
assert_type(data_source(users), DataSource[User])
assert_type(data_source(mapping), DataSource[dict[str, str]])
assert_type(data_source(User("Ada")), DataSource[User])
