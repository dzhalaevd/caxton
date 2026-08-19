"""Coordinate spreadsheet structural validation in diagnostic order."""

from __future__ import annotations

from caxton._internal.validation.features import validate_spreadsheet_features
from caxton._internal.validation.formulas import validate_formula_references
from caxton._internal.validation.structure import (
    validate_chart_sources,
    validate_document_shape,
    validate_placement,
    validate_tables,
    validate_worksheet_names,
)
from caxton.core.errors import Notification
from caxton.core.models import SpreadsheetDocument


def validate_spreadsheet(document: SpreadsheetDocument) -> None:
    """Validate a spreadsheet graph without reading any data source."""
    notification = Notification()
    validate_document_shape(document, notification)
    validate_worksheet_names(document, notification)
    validate_tables(document, notification)
    validate_spreadsheet_features(document, notification)
    validate_formula_references(document, notification)
    validate_chart_sources(document, notification)
    validate_placement(document, notification)
    notification.raise_if_errors("Spreadsheet structural validation failed")


__all__ = ("validate_spreadsheet",)
