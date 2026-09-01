import dataclasses
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from caxton import (
    DataSourceConsumedError,
    decimal,
    field,
    integer,
    money,
    path,
    sheet,
    spreadsheet,
    table,
    text,
)
from caxton.core.formatting import Alignment, decimal_format
from caxton.core.models import (
    BinaryExpression,
    Column,
    FieldRef,
    LiteralExpression,
    PathRef,
    SpreadsheetDocument,
    SpreadsheetTable,
    Stack,
    TableData,
    Worksheet,
)
from caxton.core.protocols import DataSourceInfo, Repeatability
from caxton.core.types import Decimal
from caxton.testing import inspect_spec


class _MutableLeaf:
    pass


class _EmptySource:
    def iter_rows(self) -> Iterator[object]:
        return iter(())

    def get_value(self, _row: object, _field: str) -> object:
        return object()


_FOREIGN_NODE: Any = object()


def test_readme_example_builds_semantic_graph() -> None:
    rows = [{"manager": "Ada", "revenue": 100}]

    document = spreadsheet(
        sheet(
            "Sales",
            table(
                rows,
                text("manager").titled("Manager"),
                money("revenue").titled("Revenue"),
                name="sales",
            ),
        ),
        metadata={"locale": "en"},
    )

    assert isinstance(document, SpreadsheetDocument)
    inspected = inspect_spec(document)
    revenue = inspected.worksheet("Sales").table("sales").column("revenue")
    assert revenue.title == "Revenue"
    assert revenue.source is not None
    assert revenue.source.kind == "field"
    assert revenue.source.value == "revenue"


def test_column_operations_are_generative() -> None:  # noqa: WPS218
    base = money("revenue")
    titled = base.titled("Revenue")
    styled = titled.width(20).align("right")

    assert base.display_title == "revenue"
    assert base.width_hint is None
    assert titled.display_title == "Revenue"
    assert titled.width_hint is None
    assert styled.width_hint == 20
    assert styled.alignment is Alignment.RIGHT


def test_nested_collections_are_copied() -> None:
    columns = [text("name")]
    blocks = [table([], *columns)]
    worksheets = [sheet("People", *blocks)]
    metadata = {"owner": "team"}

    document = spreadsheet(*worksheets, metadata=metadata)
    columns.append(integer("age"))
    blocks.clear()
    worksheets.clear()
    metadata["owner"] = "other"

    assert len(document.worksheets) == 1
    assert len(document.worksheets[0].blocks) == 1
    assert len(document.worksheets[0].tables[0].columns) == 1
    assert document.metadata["owner"] == "team"
    with pytest.raises(TypeError):
        document.metadata["new"] = "value"  # type: ignore[index]


def test_direct_model_freezes_nested_collections() -> None:
    name_column = text("name")
    columns = [name_column]
    semantic_table = SpreadsheetTable(
        data=TableData(source=_EmptySource(), columns=columns),
    )
    blocks = [semantic_table]
    worksheet = Worksheet(name="People", blocks=blocks)
    worksheets = [worksheet]

    document = SpreadsheetDocument(worksheets=worksheets)
    columns.append(integer("age"))
    blocks.clear()
    worksheets.clear()

    assert document.worksheets == (worksheet,)
    assert worksheet.blocks == (semantic_table,)
    assert semantic_table.columns == (name_column,)


@pytest.mark.parametrize(
    ("construct", "message"),
    [
        (
            lambda: TableData(source=_EmptySource(), columns=(_FOREIGN_NODE,)),
            "Table columns must be Column values",
        ),
        (
            lambda: SpreadsheetTable(data=_FOREIGN_NODE),
            "Spreadsheet table data must be a TableData value",
        ),
        (
            lambda: Stack(items=(_FOREIGN_NODE,)),
            "Stack items must be spreadsheet blocks",
        ),
        (
            lambda: Worksheet(name="Data", blocks=(_FOREIGN_NODE,)),
            "Worksheet blocks must be spreadsheet blocks",
        ),
        (
            lambda: SpreadsheetDocument(worksheets=(_FOREIGN_NODE,)),
            "Spreadsheet worksheets must be Worksheet values",
        ),
    ],
)
def test_direct_model_rejects_foreign_nodes(
    construct: Callable[[], object],
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        construct()


def test_metadata_is_deeply_frozen() -> None:
    labels = ["draft"]
    owners = {"Ada"}
    details = {"labels": labels, "owners": owners}

    document = spreadsheet(metadata={"details": details})
    labels.append("final")
    owners.add("Grace")

    frozen = document.metadata["details"]
    assert frozen["labels"] == ("draft",)  # type: ignore[index]
    assert frozen["owners"] == frozenset(("Ada",))  # type: ignore[index]


def test_metadata_rejects_mutable_leaf() -> None:
    with pytest.raises(TypeError, match="_MutableLeaf"):
        spreadsheet(metadata={"value": _MutableLeaf()})


def test_literal_keeps_scalar_cell_values() -> None:
    literal = LiteralExpression("draft")

    assert literal.value == "draft"


@pytest.mark.parametrize("value", [["draft"], {"label": "draft"}, _MutableLeaf()])
def test_literal_rejects_non_cell_values(value: object) -> None:
    with pytest.raises(TypeError, match="Unsupported cell value"):
        LiteralExpression(value)


def test_column_requires_source_or_formula() -> None:
    with pytest.raises(ValueError, match="either a Python source"):
        Column(id="amount", semantic_type=Decimal(), source=None)


def test_frozen_nodes_reject_direct_mutation() -> None:
    column = text("name")

    with pytest.raises(dataclasses.FrozenInstanceError):
        column.id = "other"  # type: ignore[misc]


def test_identity_is_separate_from_source() -> None:  # noqa: WPS218
    direct = text("name", source="full_name")
    nested = text("manager", source=path("manager", "name"))
    computed = decimal("delta", source=field("price") - field("base_price"))

    assert direct.id == "name"
    assert isinstance(direct.source, FieldRef)
    assert direct.source.name == "full_name"
    assert isinstance(nested.source, PathRef)
    assert nested.source.segments == ("manager", "name")
    assert isinstance(computed.source, BinaryExpression)


def test_path_ref_copies_direct_sequence_input() -> None:
    segments = ["customer", "name"]

    reference = PathRef(segments)
    segments.append("value")

    assert reference.segments == ("customer", "name")


def test_expression_rejects_boolean_context() -> None:
    comparison = field("left") == field("right")

    with pytest.raises(TypeError, match="boolean"):
        bool(comparison)


def test_formatting_is_generative() -> None:
    base = decimal("amount")
    formatted = base.format(decimal_format(places=3))

    assert base.display_format is None
    assert formatted.display_format == decimal_format(places=3)


def test_table_keeps_generator_lazy() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"id": 1}

    semantic_table = table(rows(), integer("id"))

    assert not visited
    assert isinstance(semantic_table.data.source, DataSourceInfo)
    assert semantic_table.data.source.repeatability is Repeatability.ONE_SHOT
    assert list(semantic_table.data.source.iter_rows()) == [{"id": 1}]
    assert visited
    with pytest.raises(DataSourceConsumedError):
        semantic_table.data.source.iter_rows()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_width_must_be_positive(value: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        text("name").width(value)
