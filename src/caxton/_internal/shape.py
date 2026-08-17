"""Shape predicates shared by spreadsheet planning and execution."""

from caxton.core.models import AggregateExpr, SpreadsheetTable


def table_needs_preparation(table: SpreadsheetTable) -> bool:
    """Return whether a table needs grouped or aggregate buffering."""
    return any(
        column.grouping is not None or isinstance(column.source, AggregateExpr)
        for column in table.columns
    )


__all__ = ("table_needs_preparation",)
