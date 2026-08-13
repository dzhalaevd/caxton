import dataclasses
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

from caxton import (
    DataSourceConsumedError,
    FieldAccessError,
    MissingFieldError,
    UnsupportedDataSourceError,
    table,
    text,
)
from caxton._internal.data import (  # noqa: PLC2701
    AttributeRowAccessor,
    MappingRowAccessor,
    coerce_data_source,
)
from caxton.core.protocols import (
    DataSource,
    DataSourceInfo,
    Repeatability,
    RowAccessor,
)


@dataclasses.dataclass
class User:
    name: str
    age: int


class NamedUser(NamedTuple):
    name: str
    age: int


class UserObject:  # noqa: B903
    def __init__(self, name: str) -> None:
        self.name = name


class BrokenUser:
    @property
    def name(self) -> str:
        message = "database session is closed"
        raise RuntimeError(message)


class AttributeErrorUser:
    @property
    def name(self) -> str:
        message = "descriptor failed internally"
        raise AttributeError(message)


class QuerySetLike:
    def __init__(self) -> None:
        self.iter_calls = 0
        self.len_calls = 0

    def __iter__(self) -> Iterator[User]:
        self.iter_calls += 1
        yield User("Ada", 37)

    def __len__(self) -> int:
        self.len_calls += 1
        message = "coercion must not ask a lazy source for its length"
        raise AssertionError(message)


class CustomDataSource:
    def iter_rows(self) -> Iterator[dict[str, str]]:
        yield {"alias": "Ada"}

    def get_value(self, row: dict[str, str], field: str) -> object:
        return row[{"name": "alias"}.get(field, field)]


class LowercaseAccessor:
    def __call__(self, row: Mapping[str, str], field: str) -> object:
        return row[field.lower()]


def test_list_of_dicts_uses_one_lazy_data_source() -> None:
    rows = [{"name": "Ada"}, {"name": "Grace"}]

    source = coerce_data_source(rows)
    materialized = list(source.iter_rows())

    assert isinstance(source, DataSource)
    assert isinstance(source, DataSourceInfo)
    assert source.repeatability is Repeatability.REITERABLE
    assert source.row_count == 2
    assert [source.get_value(row, "name") for row in materialized] == [
        "Ada",
        "Grace",
    ]


def test_mapping_reports_missing_field() -> None:
    accessor = MappingRowAccessor()
    row = {"name": "Ada"}

    with pytest.raises(MissingFieldError) as captured:
        accessor(row, "email")

    error = captured.value
    assert error.field == "email"
    assert error.row_type == "dict"
    assert error.row_index is None
    assert error.context == {
        "field": "email",
        "row_index": None,
        "row_type": "dict",
    }
    assert isinstance(error.__cause__, KeyError)


def test_object_shapes_use_attributes() -> None:
    inputs = (
        [User("Ada", 37)],
        NamedUser("Grace", 85),
        UserObject("Linus"),
    )

    values = []
    for input_rows in inputs:
        source = coerce_data_source(input_rows)
        row = next(source.iter_rows())
        values.append(source.get_value(row, "name"))

    assert values == ["Ada", "Grace", "Linus"]


@pytest.mark.parametrize("row", [BrokenUser(), AttributeErrorUser()])
def test_descriptor_failure_is_not_missing(row: object) -> None:
    accessor = AttributeRowAccessor()

    with pytest.raises(FieldAccessError) as captured:
        accessor(row, "name")

    error = captured.value
    assert error.field == "name"
    assert error.row_type == type(row).__name__
    assert error.context["exception_type"] in {"RuntimeError", "AttributeError"}
    assert error.__cause__ is not None


def test_absent_attribute_is_a_missing_field() -> None:
    accessor = AttributeRowAccessor()

    with pytest.raises(MissingFieldError) as captured:
        accessor(UserObject("Ada"), "email")

    assert captured.value.field == "email"
    assert isinstance(captured.value.__cause__, AttributeError)


def test_generator_is_lazy_and_one_shot() -> None:  # noqa: WPS218
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"name": "Ada"}

    source = coerce_data_source(rows())

    assert not visited
    assert isinstance(source, DataSourceInfo)
    assert source.repeatability is Repeatability.ONE_SHOT
    assert source.row_count is None
    assert list(source.iter_rows()) == [{"name": "Ada"}]
    assert visited
    with pytest.raises(DataSourceConsumedError):
        source.iter_rows()


def test_queryset_is_lazy_during_coercion() -> None:  # noqa: WPS218
    rows = QuerySetLike()

    source = coerce_data_source(rows)

    assert rows.iter_calls == 0
    assert rows.len_calls == 0
    assert isinstance(source, DataSourceInfo)
    assert source.repeatability is Repeatability.UNKNOWN
    assert source.row_count is None
    assert list(source.iter_rows()) == [User("Ada", 37)]
    assert rows.iter_calls == 1
    assert rows.len_calls == 0


def test_custom_source_passes_through_table() -> None:
    source = CustomDataSource()

    semantic_table = table(source, text("name"))
    row = next(semantic_table.data.source.iter_rows())

    assert semantic_table.data.source is source
    assert semantic_table.data.source.get_value(row, "name") == "Ada"


def test_explicit_custom_row_accessor_is_used() -> None:
    accessor = LowercaseAccessor()
    source = coerce_data_source([{"name": "Ada"}], accessor=accessor)
    row = next(source.iter_rows())

    assert isinstance(accessor, RowAccessor)
    assert source.get_value(row, "NAME") == "Ada"


def test_opaque_object_is_not_implicitly_a_row() -> None:
    with pytest.raises(UnsupportedDataSourceError):
        coerce_data_source(Path("report.xlsx"))
