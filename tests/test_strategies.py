from hypothesis import given, settings

from caxton import validate
from caxton.core.models import SpreadsheetDocument
from caxton.testing import canonical_snapshot, inspect_spec
from caxton.testing.strategies import spreadsheet_documents


@given(spreadsheet_documents())
@settings(max_examples=25)
def test_generated_spreadsheets_are_valid(
    document: SpreadsheetDocument,
) -> None:
    validate(document)
    snapshot = canonical_snapshot(inspect_spec(document))

    assert snapshot.endswith("\n")
