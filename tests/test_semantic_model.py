import dataclasses
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from caxton import (
    DataSourceConsumedError,
    boolean,
    date,
    datetime,
    decimal,
    duration,
    field,
    integer,
    link,
    money,
    path,
    percentage,
    sheet,
    spreadsheet,
    table,
    text,
    time,
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
    TransformExpression,
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
                source=rows,
                columns=(
                    text(id="manager", source="manager", title="Manager"),
                    money(id="revenue", source="revenue", title="Revenue"),
                ),
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
    base = money(id="revenue", source="revenue")
    titled = base.titled("Revenue")
    styled = titled.width(20).align("right")

    assert base.display_title == "revenue"
    assert base.width_hint is None
    assert titled.display_title == "Revenue"
    assert titled.width_hint is None
    assert styled.width_hint == 20
    assert styled.alignment is Alignment.RIGHT


@pytest.mark.parametrize(
    "factory",
    [
        boolean,
        date,
        datetime,
        decimal,
        duration,
        integer,
        link,
        money,
        percentage,
        text,
        time,
    ],
)
def test_factories_accept_title(
    factory: Callable[..., Column],
) -> None:
    result = factory(id="value", source="value", title="Display value")

    assert result.id == "value"
    assert result.title == "Display value"
    assert result.display_title == "Display value"


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        (1, TypeError, "Column title must be a string"),
        (" ", ValueError, "Column title cannot be empty"),
    ],
)
def test_factory_validates_title(
    value: Any,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        text(id="value", source="value", title=value)


def test_nested_collections_are_copied() -> None:
    columns = [text(id="name", source="name")]
    blocks = [table(source=[], columns=columns)]
    worksheets = [sheet("People", *blocks)]
    metadata = {"owner": "team"}

    document = spreadsheet(*worksheets, metadata=metadata)
    columns.append(integer(id="age", source="age"))
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
    name_column = text(id="name", source="name")
    columns = [name_column]
    semantic_table = SpreadsheetTable(
        data=TableData(source=_EmptySource(), columns=columns),
    )
    blocks = [semantic_table]
    worksheet = Worksheet(name="People", blocks=blocks)
    worksheets = [worksheet]

    document = SpreadsheetDocument(worksheets=worksheets)
    columns.append(integer(id="age", source="age"))
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


def test_transform_is_explicit_immutable_intent() -> None:
    def title(value: object) -> str:
        return str(value).title()

    expression = field("status").transform(title)

    assert isinstance(expression, TransformExpression)
    assert isinstance(expression.expression, FieldRef)
    assert expression.expression.name == "status"
    assert expression.function is title


def test_expression_transform_requires_callable() -> None:
    with pytest.raises(TypeError, match="must be callable"):
        field("status").transform("title")  # type: ignore[arg-type]


def test_column_requires_source_or_formula() -> None:
    with pytest.raises(ValueError, match="either a Python source"):
        Column(id="amount", semantic_type=Decimal(), source=None)


@pytest.mark.parametrize(
    ("replace_with", "message"),
    [
        ({"semantic_type": "decimal"}, "semantic type"),
        ({"alignment": "right"}, "alignment"),
        ({"display_format": object()}, "display format"),
        ({"style_ref": object()}, "style"),
        ({"width_hint": 0}, "width"),
    ],
)
def test_direct_column_enforces_field_contracts(
    replace_with: dict[str, object],
    message: str,
) -> None:
    valid = decimal(id="amount", source="amount")

    with pytest.raises(TypeError if message != "width" else ValueError, match=message):
        dataclasses.replace(valid, **replace_with)  # type: ignore[arg-type]


def test_column_factory_rejects_invalid_style() -> None:
    with pytest.raises(TypeError, match="style"):
        text(source="name", style=object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("replace_with", "message"),
    [
        ({"styles": {}}, "styles"),
        ({"theme": {}}, "theme"),
    ],
)
def test_direct_document_enforces_field_contracts(
    replace_with: dict[str, object],
    message: str,
) -> None:
    document = SpreadsheetDocument(worksheets=())

    with pytest.raises(TypeError, match=message):
        dataclasses.replace(document, **replace_with)  # type: ignore[arg-type]


def test_expression_hash_remains_identity_based() -> None:
    expression = field("amount")

    assert {expression: "cached"}[expression] == "cached"


def test_frozen_nodes_reject_direct_mutation() -> None:
    name_column = text(id="name", source="name")

    with pytest.raises(dataclasses.FrozenInstanceError):
        name_column.id = "other"  # type: ignore[misc]


def test_identity_is_separate_from_source() -> None:  # noqa: WPS218
    direct = text(id="name", source="full_name")
    nested = text(id="manager", source=path("manager", "name"))
    computed = decimal(id="delta", source=field("price") - field("base_price"))

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
    base = decimal(id="amount", source="amount")
    formatted = base.format(decimal_format(places=3))

    assert base.display_format is None
    assert formatted.display_format == decimal_format(places=3)


def test_table_keeps_generator_lazy() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"id": 1}

    semantic_table = table(source=rows(), columns=(integer(id="id", source="id"),))

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
        text(id="name", source="name").width(value)
