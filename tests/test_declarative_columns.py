import dataclasses
import datetime as dt
import decimal as decimal_module
from collections.abc import Mapping
from typing import ClassVar, cast, get_args, get_type_hints

import pytest

from caxton import (
    AutoWidth,
    Boolean,
    CaxtonTypeError,
    CaxtonValueError,
    Column,
    ColumnSchema,
    Date,
    DateTime,
    Decimal,
    Duration,
    FieldRef,
    Formula,
    Integer,
    Link,
    LiteralExpression,
    Money,
    Percentage,
    SemanticType,
    Style,
    Text,
    Time,
    Total,
    ValidationError,
    api as public_api,
    boolean,
    col,
    date,
    datetime,
    decimal,
    duration,
    field,
    integer,
    link,
    literal,
    money,
    percentage,
    sheet,
    spreadsheet,
    table,
    text,
    time,
    validate,
)
from caxton.core.formatting import Alignment
from caxton.testing import Rows, inspect_layout, inspect_spec


class Rating(SemanticType):
    name: ClassVar[str] = "rating"
    numeric: ClassVar[bool] = True


def test_literal_normalizes_every_supported_scalar() -> None:
    values = (
        None,
        True,
        dt.date(2026, 9, 8),
        dt.datetime(2026, 9, 8, 12, 30, tzinfo=dt.timezone.utc),
        dt.time(12, 30),
        dt.timedelta(minutes=5),
        decimal_module.Decimal("1.5"),
        1.5,
        1,
        "ready",
    )

    assert tuple(literal(value).value for value in values) == values
    assert all(isinstance(literal(value), LiteralExpression) for value in values)


def test_literal_rejects_unsupported_values_with_exception_chaining() -> None:
    with pytest.raises(CaxtonTypeError, match="Unsupported cell value") as captured:
        literal(["ready"])  # type: ignore[arg-type]

    assert isinstance(captured.value.__cause__, TypeError)


def test_literal_remains_visible_to_semantic_inspection() -> None:
    column = Column(
        semantic_type=Text(),
        id="status",
        source=literal("ready"),
    )
    document = spreadsheet(
        sheet("Data", table(source=[], columns=(column,), name="values")),
    )

    inspected = inspect_spec(document).worksheet("Data").table("values")

    source = inspected.column("status").source
    assert source is not None
    assert source.value == "ready"


def test_literal_annotation_matches_runtime_scalar_domain() -> None:
    annotation = get_type_hints(literal)["value"]

    assert set(get_args(annotation)) == {
        type(None),
        bool,
        dt.date,
        dt.datetime,
        dt.time,
        dt.timedelta,
        decimal_module.Decimal,
        float,
        int,
        str,
    }


def test_column_constructs_custom_semantic_type_and_normalizes_state() -> None:
    style = Style()
    column = Column(
        semantic_type=Rating(),
        source="rating",
        title="Rating",
        alignment="right",
        style=style,
        auto_width=True,
    )

    assert column.id == "rating"
    assert isinstance(column.source, FieldRef)
    assert column.source.name == "rating"
    assert column.excel_formula is None
    assert column.alignment is Alignment.RIGHT
    assert column.style is style
    assert column.auto_width == AutoWidth()


def test_column_dataclass_contract_and_keyword_only_constructor() -> None:
    parameters = {field.name: field.type for field in dataclasses.fields(Column)}

    assert parameters["id"] == "str"
    assert parameters["source"] == "ColumnSource | None"
    assert parameters["excel_formula"] == "Formula | None"
    assert parameters["alignment"] == "Alignment | None"
    assert parameters["auto_width"] == "AutoWidth | None"
    assert "style" in parameters
    assert "style_ref" not in parameters
    with pytest.raises(TypeError):
        Column(  # type: ignore[call-arg]
            "rating",  # type: ignore[arg-type]
            Rating(),  # type: ignore[arg-type]
            field("rating"),
        )


@pytest.mark.parametrize(
    "semantic_type",
    [Rating, str, "rating", text],
)
def test_column_requires_semantic_type_instance(semantic_type: object) -> None:
    with pytest.raises(CaxtonTypeError, match="SemanticType"):
        Column(semantic_type=semantic_type, source="rating")  # type: ignore[arg-type]


def test_column_distinguishes_source_exclusion_errors() -> None:
    with pytest.raises(CaxtonValueError, match="A column requires either a Python"):
        Column(semantic_type=Rating())
    with pytest.raises(CaxtonValueError, match="Column 'rating' cannot define both"):
        Column(
            semantic_type=Rating(),
            source="rating",
            excel_formula=col("rating"),
        )


def test_column_exclusion_errors_name_the_declared_id() -> None:
    with pytest.raises(CaxtonValueError, match="Column 'total' requires either"):
        Column(semantic_type=Rating(), id="total")


@pytest.mark.parametrize(
    "source_or_formula",
    [
        {"source": field("rating")},
        {"source": lambda row: row},
        {"excel_formula": col("rating")},
    ],
)
def test_column_requires_id_without_exact_string_source(
    source_or_formula: dict[str, object],
) -> None:
    with pytest.raises(CaxtonValueError, match="explicit column ID is required"):
        Column(semantic_type=Rating(), **source_or_formula)  # type: ignore[arg-type]


def test_column_normalizes_formula_and_rejects_competing_widths() -> None:
    formula_column = Column(
        semantic_type=Decimal(),
        id="total",
        excel_formula=col("amount") * 2,
    )

    assert isinstance(formula_column.excel_formula, Formula)
    with pytest.raises(CaxtonValueError, match="explicit width"):
        Column(
            semantic_type=Text(),
            source="name",
            width_hint=10,
            auto_width=True,
        )


def test_width_hint_rejects_the_fluent_auto_keyword() -> None:
    with pytest.raises(CaxtonTypeError, match="width must be numeric"):
        Column(
            semantic_type=Text(),
            source="name",
            width_hint="auto",  # type: ignore[arg-type]
        )

    fluent = Column(semantic_type=Text(), source="name").width("auto")

    assert fluent.auto_width == AutoWidth()
    assert fluent.width_hint is None


def test_dataclasses_replace_uses_friendly_inputs_without_reinferring_id() -> None:
    original = Column(semantic_type=Text(), id="label", source="name")

    replaced = dataclasses.replace(
        original,
        source="other",  # type: ignore[arg-type]
        alignment="center",  # type: ignore[arg-type]
        auto_width=True,  # type: ignore[arg-type]
    )

    assert replaced.id == "label"
    assert isinstance(replaced.source, FieldRef)
    assert replaced.source.name == "other"
    assert replaced.alignment is Alignment.CENTER
    assert replaced.auto_width == AutoWidth()


@pytest.mark.parametrize(
    ("factory", "semantic_type", "factory_options"),
    [
        (boolean, Boolean(), {}),
        (date, Date(), {}),
        (datetime, DateTime(), {}),
        (decimal, Decimal(), {}),
        (duration, Duration(), {}),
        (integer, Integer(), {}),
        (link, Link(), {}),
        (money, Money(currency="RUB"), {"currency": "RUB"}),
        (percentage, Percentage(), {}),
        (text, Text(), {}),
        (time, Time(), {}),
    ],
)
def test_factories_match_generic_column_semantics(
    factory: object,
    semantic_type: SemanticType,
    factory_options: dict[str, object],
) -> None:
    style = Style()
    factory_column = factory(  # type: ignore[operator]
        id="value",
        source="source_value",
        title="Value",
        style=style,
        **factory_options,
    )
    generic_column = Column(
        semantic_type=semantic_type,
        id="value",
        source="source_value",
        title="Value",
        style=style,
    )

    def inspected(column: Column) -> object:
        document = spreadsheet(
            sheet("Data", table(source=[], columns=(column,), name="values")),
        )
        return inspect_spec(document).worksheet("Data").table("values").columns[0]

    assert inspected(factory_column) == inspected(generic_column)


def test_semantic_types_are_exported_from_both_public_facades() -> None:
    exported = (
        SemanticType,
        Boolean,
        Date,
        DateTime,
        Decimal,
        Duration,
        Integer,
        Link,
        Money,
        Percentage,
        Text,
        Time,
    )

    assert all(getattr(public_api, item.__name__) is item for item in exported)


def test_schema_collects_columns_in_declaration_order() -> None:
    class CommonColumns(ColumnSchema):
        helper = "ignored"
        name = Column(semantic_type=Text(), source="name")
        _private = Column(semantic_type=Text(), source="private")
        amount = money(source="amount")
        nested = (Column(semantic_type=Text(), source="nested"),)

    assert CommonColumns.columns == (CommonColumns.name, CommonColumns.amount)
    assert CommonColumns.helper == "ignored"
    assert CommonColumns.nested[0].id == "nested"


def test_empty_schema_is_valid_and_table_validation_rejects_empty_columns() -> None:
    class EmptyColumns(ColumnSchema):
        pass

    document = spreadsheet(
        sheet("Data", table(source=[], columns=EmptyColumns.columns)),
    )

    assert not ColumnSchema.columns
    assert not EmptyColumns.columns
    with pytest.raises(ValidationError) as captured:
        validate(document)
    assert {issue.code for issue in captured.value.issues} == {"missing_column"}


def test_schema_inheritance_replaces_in_place_and_appends_new_columns() -> None:
    class BaseColumns(ColumnSchema):
        name = Column(semantic_type=Text(), source="name")
        amount = Column(semantic_type=Decimal(), source="amount")

    class ExportColumns(BaseColumns):
        amount = BaseColumns.amount.titled("Total amount")
        created_at = Column(semantic_type=DateTime(), source="created_at")

    assert ExportColumns.columns == (
        BaseColumns.name,
        ExportColumns.amount,
        ExportColumns.created_at,
    )


def test_schema_rebinding_does_not_rebuild_canonical_columns() -> None:
    class Columns(ColumnSchema):
        name = Column(semantic_type=Text(), source="name")

    original = Columns.name
    Columns.name = Columns.name.titled("Changed")

    assert Columns.name is not original
    assert Columns.columns == (original,)


def test_dynamic_schema_creation_uses_the_same_collection_rules() -> None:
    first = Column(semantic_type=Text(), source="first")
    second = Column(semantic_type=Integer(), source="second")

    generated = cast(
        "type[ColumnSchema]",
        type(
            "GeneratedColumns",
            (ColumnSchema,),
            {"first": first, "second": second},
        ),
    )

    assert generated.columns == (first, second)


def test_schema_reports_attribute_id_mismatch_with_stable_path() -> None:
    with pytest.raises(CaxtonValueError) as captured:
        type(
            "MismatchedColumns",
            (ColumnSchema,),
            {"amount": Column(semantic_type=Decimal(), source="total")},
        )

    assert captured.value.path == 'schema["MismatchedColumns"].column["amount"]'


@pytest.mark.parametrize(
    "declared",
    [
        (),
        "columns",
        Column(semantic_type=Text(), source="columns"),
    ],
)
def test_schema_rejects_reserved_columns_name(declared: object) -> None:
    with pytest.raises(CaxtonValueError) as captured:
        type("ReservedColumns", (ColumnSchema,), {"columns": declared})

    assert captured.value.path == 'schema["ReservedColumns"].column["columns"]'


def test_schema_rejects_removing_inherited_column_by_shadowing() -> None:
    class BaseColumns(ColumnSchema):
        name = Column(semantic_type=Text(), source="name")

    with pytest.raises(CaxtonTypeError) as captured:
        type("RemovedColumns", (BaseColumns,), {"name": None})

    assert captured.value.path == 'schema["RemovedColumns"].column["name"]'


def test_schema_rejects_multiple_inheritance_and_recommends_composition() -> None:
    class Helper:
        pass

    with pytest.raises(CaxtonTypeError, match="tuple composition"):
        type("MixedColumns", (ColumnSchema, Helper), {})


def test_schema_classes_cannot_be_instantiated() -> None:
    class Columns(ColumnSchema):
        pass

    with pytest.raises(CaxtonTypeError) as captured:
        Columns()

    assert captured.value.path == f'schema["{Columns.__qualname__}"]'


def test_table_suggests_columns_for_exact_schema_class() -> None:
    class Columns(ColumnSchema):
        name = Column(semantic_type=Text(), source="name")

    with pytest.raises(CaxtonTypeError, match=r"Columns\.columns"):
        table(source=[], columns=Columns)  # type: ignore[arg-type]


def test_table_keeps_generic_error_for_unrelated_class() -> None:
    class Columns:
        pass

    with pytest.raises(CaxtonTypeError, match="sequence of Column values") as captured:
        table(source=[], columns=Columns)  # type: ignore[arg-type]

    assert ".columns" not in str(captured.value)


def test_schema_order_controls_grouping_hierarchy() -> None:
    rows = (
        {"region": "North", "shop": "B", "value": 1},
        {"region": "North", "shop": "A", "value": 2},
        {"region": "South", "shop": "A", "value": 3},
    )

    class RegionFirst(ColumnSchema):
        region = Column(semantic_type=Text(), source="region").grouped(
            order="ascending",
        )
        shop = Column(semantic_type=Text(), source="shop").grouped(
            order="ascending",
        )
        total = Column(
            semantic_type=Decimal(),
            id="total",
            source=field("value").agg(sum),
        )

    class ShopFirst(ColumnSchema):
        shop = RegionFirst.shop
        region = RegionFirst.region
        total = RegionFirst.total

    def values(schema: type[ColumnSchema]) -> list[Mapping[str, object]]:
        document = spreadsheet(
            sheet("Summary", table(source=rows, columns=schema.columns)),
        )
        layout = inspect_layout(document, rows=Rows.all())
        return [row.values for row in layout.worksheet("Summary").tables[0].rows]

    assert [(row["region"], row["shop"]) for row in values(RegionFirst)] == [
        ("North", "A"),
        ("North", "B"),
        ("South", "A"),
    ]
    assert [(row["shop"], row["region"]) for row in values(ShopFirst)] == [
        ("A", "North"),
        ("A", "South"),
        ("B", "North"),
    ]


def test_schema_order_changes_implicit_totals_label_position() -> None:
    class LabelFirst(ColumnSchema):
        label = Column(semantic_type=Text(), source="label")
        amount = Column(semantic_type=Decimal(), source="amount")

    class AmountFirst(ColumnSchema):
        amount = LabelFirst.amount
        label = LabelFirst.label

    def total_label_offset(schema: type[ColumnSchema]) -> int:
        document = spreadsheet(
            sheet(
                "Summary",
                table(
                    source=[{"label": "A", "amount": 1}],
                    columns=schema.columns,
                    footer=(Total("amount"),),
                ),
            ),
        )
        layout = inspect_layout(document)
        footer = layout.worksheet("Summary").tables[0].footer
        assert footer is not None
        return footer.label_column_offset

    assert total_label_offset(LabelFirst) == 0
    assert total_label_offset(AmountFirst) == 1
