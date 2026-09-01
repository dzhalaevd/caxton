import string

from hypothesis import strategies as st

from caxton.api import sheet, spreadsheet, table
from caxton.core.formatting import Alignment
from caxton.core.models import Column, FieldRef, SpreadsheetDocument
from caxton.core.types import (
    Boolean,
    Date,
    DateTime,
    Decimal,
    Duration,
    Integer,
    Link,
    Money,
    Percentage,
    SemanticType,
    Text,
    Time,
)

_IDENTIFIER_START = string.ascii_lowercase
_IDENTIFIER_REST = f"{string.ascii_lowercase}{string.digits}_"
_CURRENCIES = (None, "EUR", "GBP", "RUB", "USD")


def identifiers() -> st.SearchStrategy[str]:
    """Generate compact identifiers accepted by Caxton models.

    Returns:
        An identifier strategy.
    """
    return st.builds(
        str.__add__,
        st.sampled_from(tuple(_IDENTIFIER_START)),
        st.text(alphabet=_IDENTIFIER_REST, max_size=11),
    )


def semantic_types() -> st.SearchStrategy[SemanticType]:
    """Generate built-in semantic type declarations.

    Returns:
        A semantic type strategy.
    """
    fixed = st.sampled_from(
        (
            Boolean(),
            Date(),
            DateTime(),
            Decimal(),
            Duration(),
            Integer(),
            Link(),
            Percentage(),
            Text(),
            Time(),
        ),
    )
    return st.one_of(
        fixed,
        st.builds(Money, currency=st.sampled_from(_CURRENCIES)),
    )


@st.composite
def columns(draw: st.DrawFn) -> Column:
    """Generate one valid semantic column.

    Returns:
        A generated column.
    """
    column_id = draw(identifiers())
    column = Column(
        id=column_id,
        semantic_type=draw(semantic_types()),
        source=FieldRef(column_id),
    )
    if draw(st.booleans()):
        column = column.titled(draw(identifiers()))
    if draw(st.booleans()):
        column = column.align(draw(st.sampled_from(tuple(Alignment))))
    if draw(st.booleans()):
        column = column.width(
            draw(st.floats(min_value=1, max_value=100, allow_nan=False)),
        )
    return column


@st.composite
def spreadsheet_documents(draw: st.DrawFn) -> SpreadsheetDocument:
    """Generate a bounded, structurally valid spreadsheet declaration.

    Returns:
        A generated spreadsheet document.
    """
    worksheet_names = draw(
        st.lists(identifiers(), min_size=1, max_size=3, unique=True),
    )
    table_counts = draw(
        st.lists(
            st.integers(min_value=0, max_value=3),
            min_size=len(worksheet_names),
            max_size=len(worksheet_names),
        ),
    )
    table_names = iter(
        draw(
            st.lists(
                identifiers(),
                min_size=sum(table_counts),
                max_size=sum(table_counts),
                unique=True,
            ),
        ),
    )
    worksheets = []
    for worksheet_name, table_count in zip(worksheet_names, table_counts, strict=True):
        use_explicit_anchors = draw(st.booleans())
        tables = []
        for table_index in range(table_count):
            table_name = next(table_names)
            generated_columns = draw(
                st.lists(
                    columns(),
                    min_size=1,
                    max_size=5,
                    unique_by=lambda column: column.id,
                ),
            )
            tables.append(
                table(
                    source=[],
                    columns=generated_columns,
                    name=table_name,
                    anchor=(
                        f"A{table_index * 3 + 1}"
                        if use_explicit_anchors or table_index > 0
                        else None
                    ),
                ),
            )
        worksheets.append(sheet(worksheet_name, *tables))
    metadata = draw(
        st.dictionaries(
            identifiers(),
            st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=20)),
            max_size=3,
        ),
    )
    return spreadsheet(*worksheets, metadata=metadata)


__all__ = (
    "columns",
    "identifiers",
    "semantic_types",
    "spreadsheet_documents",
)
