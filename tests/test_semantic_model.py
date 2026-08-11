import dataclasses
from collections.abc import Iterator

import pytest

from formata import (
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
from formata.core.formatting import Alignment, decimal_format
from formata.core.models import (
    BinaryExpression,
    FieldRef,
    Literal,
    PathRef,
    SpreadsheetDocument,
)
from formata.core.protocols import DataSourceInfo, Repeatability
from formata.testing import inspect_spec


class _MutableLeaf:
    pass


def test_readme_example_builds_semantic_graph() -> None:
    rows = [{"manager": "Ada", "revenue": 100}]

    document = spreadsheet(
        sheet(
            "Sales",
            table(
                rows,
                text("manager").title("Manager"),
                money("revenue").title("Revenue"),
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
    titled = base.title("Revenue")
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
    assert len(document.worksheets[0].blocks[0].columns) == 1
    assert document.metadata["owner"] == "team"
    with pytest.raises(TypeError):
        document.metadata["new"] = "value"  # type: ignore[index]


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


def test_literal_values_are_immutable_snapshots() -> None:
    values = ["draft"]
    literal = Literal(values)
    values.append("final")

    assert literal.value == ("draft",)


def test_literal_rejects_unsupported_mutable_leaf() -> None:
    with pytest.raises(TypeError, match="_MutableLeaf"):
        Literal(_MutableLeaf())


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
