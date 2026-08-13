from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
import xlsxwriter as xlsxwriter_engine  # type: ignore[import-untyped]

from caxton import (  # noqa: WPS347
    DataSourceConsumedError,
    DataSourceIterationError,
    ExecutionMode,
    UnsupportedFeatureError,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    write,
)
from caxton._internal import requirements as requirements_module  # noqa: PLC2701
from caxton._internal.backends import xlsxwriter as xlsx_backend  # noqa: PLC2701
from caxton.core.protocols import Repeatability


class _UnknownSource:
    def __init__(self) -> None:
        self.iterations = 0

    def iter_rows(self) -> Iterator[dict[str, str]]:
        self.iterations += 1
        yield {"value": "Ada"}

    def get_value(self, row: dict[str, str], field: str) -> object:
        return row[field]


def _document(rows: object, *, name: str | None = None):  # type: ignore[no-untyped-def]
    return spreadsheet(sheet("Rows", table(rows, text("value"), name=name)))


def test_requirements_are_lazy() -> None:  # noqa: WPS218
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"value": "Ada"}

    required = requirements_module.analyze_spreadsheet_requirements(
        _document(rows()),
    )

    assert not visited
    assert required.execution.mode is ExecutionMode.AUTO
    assert required.execution.append_only
    assert required.execution.requires_single_pass
    assert required.execution.data_sources[0].repeatability is Repeatability.ONE_SHOT
    assert required.execution.data_sources[0].row_count is None


def test_requirements_use_available_row_count() -> None:
    required = requirements_module.analyze_spreadsheet_requirements(
        _document([{"value": "Ada"}, {"value": "Grace"}]),
    )

    source = required.execution.data_sources[0]
    assert source.repeatability is Repeatability.REITERABLE
    assert source.row_count == 2
    assert not required.execution.requires_single_pass


def test_auto_selects_constant_memory() -> None:
    result = render(_document([{"value": "Ada"}]))

    assert result.execution_mode is ExecutionMode.STREAM
    assert result.execution_plan == "constant_memory"


def test_stream_plan_enables_xlsxwriter_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workbook_class = xlsxwriter_engine.Workbook
    observed: dict[str, bool] = {}

    def recording_workbook(filename: object, options: dict[str, bool]):  # type: ignore[no-untyped-def]
        observed.update(options)
        return workbook_class(filename, options)

    monkeypatch.setattr(xlsxwriter_engine, "Workbook", recording_workbook)

    render(_document([{"value": "Ada"}]))

    assert observed == {"constant_memory": True}


def test_standard_overrides_auto_streaming() -> None:
    result = render(_document([{"value": "Ada"}]), mode="standard")

    assert result.execution_mode is ExecutionMode.STANDARD
    assert result.execution_plan == "standard"


def test_named_table_uses_standard_plan() -> None:
    result = render(_document([{"value": "Ada"}], name="people"))

    assert result.execution_mode is ExecutionMode.STANDARD
    assert result.execution_plan == "standard"


def test_stream_rejects_native_table_early(
    tmp_path: Path,
) -> None:
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"value": "Ada"}

    target = tmp_path / "people.xlsx"

    with pytest.raises(UnsupportedFeatureError) as captured:
        write(_document(rows(), name="people"), target, mode="stream")

    assert captured.value.context["reason"] == "native_table"
    assert not visited
    assert not target.exists()


def test_stream_rejects_incompatible_backend() -> None:
    visited = False

    def rows() -> Iterator[dict[str, str]]:
        nonlocal visited
        visited = True
        yield {"value": "Ada"}

    with pytest.raises(UnsupportedFeatureError, match="lacks required"):
        render(_document(rows()), backend="openpyxl", mode="stream")

    assert not visited


def test_one_shot_fails_on_second_render() -> None:
    yielded = 0

    def rows() -> Iterator[dict[str, int]]:
        nonlocal yielded
        for index in range(5):
            yielded += 1
            yield {"value": index}

    document = _document(rows())

    first = render(document)

    assert first.execution_mode is ExecutionMode.STREAM
    assert yielded == 5
    with pytest.raises(DataSourceConsumedError):
        render(document)
    assert yielded == 5


def test_unknown_source_has_one_pass() -> None:
    source = _UnknownSource()

    result = render(_document(source))

    assert result.execution_mode is ExecutionMode.STREAM
    assert source.iterations == 1


def test_path_output_does_not_stage_in_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_staging():  # type: ignore[no-untyped-def]
        message = "unexpected staging buffer"
        raise AssertionError(message)

    monkeypatch.setattr(xlsx_backend, "BytesIO", reject_staging)
    target = tmp_path / "direct.xlsx"

    result = write(_document([{"value": "Ada"}]), target)

    assert result.bytes_written == target.stat().st_size
    assert target.read_bytes().startswith(b"PK")


def test_path_commit_happens_after_success(tmp_path: Path) -> None:
    failure = RuntimeError("database cursor failed")

    def rows() -> Iterator[dict[str, str]]:
        yield {"value": "Ada"}
        raise failure

    target = tmp_path / "existing.xlsx"
    original = b"existing artifact"
    target.write_bytes(original)

    with pytest.raises(DataSourceIterationError) as captured:
        write(_document(rows()), target)

    assert captured.value.__cause__ is failure
    assert target.read_bytes() == original


def test_seekable_output_does_not_stage_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_staging():  # type: ignore[no-untyped-def]
        message = "unexpected staging buffer"
        raise AssertionError(message)

    monkeypatch.setattr(xlsx_backend, "BytesIO", reject_staging)
    target = BytesIO()

    result = write(_document([{"value": "Ada"}]), target)

    assert result.data == target.getvalue()
    assert result.bytes_written == len(target.getvalue())
    assert target.getvalue().startswith(b"PK")


def test_large_lazy_source_streams_without_list(
    tmp_path: Path,
) -> None:
    row_count = 25_000
    yielded = 0

    def rows() -> Iterator[dict[str, int]]:
        nonlocal yielded
        for index in range(row_count):
            yielded += 1
            yield {"value": index}

    target = tmp_path / "large.xlsx"

    result = write(_document(rows()), target)

    assert yielded == row_count
    assert result.execution_mode is ExecutionMode.STREAM
    assert result.execution_plan == "constant_memory"
    assert target.stat().st_size == result.bytes_written
