from hypothesis import given, settings

from formata import validate
from formata.core.models import SpreadsheetDocument
from formata.testing import canonical_snapshot, inspect_spec
from formata.testing.strategies import spreadsheet_documents


@given(spreadsheet_documents())
@settings(max_examples=25)
def test_generated_spreadsheets_are_valid(
    document: SpreadsheetDocument,
) -> None:
    validate(document)
    snapshot = canonical_snapshot(inspect_spec(document))

    assert snapshot.endswith("\n")
