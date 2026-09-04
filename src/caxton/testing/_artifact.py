from __future__ import annotations

import dataclasses
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypeAlias, runtime_checkable

from caxton._internal.normalization import format_cell_address, parse_cell_address
from caxton.core._values import freeze_value
from caxton.core.rendering import RenderResult

from ._errors import ArtifactInspectionError


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactCell:
    """One cell observed in a materialized spreadsheet artifact.

    Formula cells expose formula text in both ``value`` and ``formula`` because
    inspection preserves formulas instead of loading calculated cached values.
    """

    address: str
    value: object
    formula: str | None
    number_format: str
    alignment: str | None
    hyperlink: str | None
    bold: bool
    font_name: str | None = None
    font_size: float | None = None
    font_color: str | None = None
    fill_color: str | None = None
    border_bottom: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            freeze_value(self.value, label="Artifact cell value"),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactColumn:
    """One observed spreadsheet column dimension."""

    letter: str
    width: float | None


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactTable:
    """One native table observed in an XLSX worksheet.

    ``row_count`` excludes the single native header row.
    """

    name: str
    cell_range: str
    column_titles: Sequence[str]
    row_count: int
    autofilter: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "column_titles", tuple(self.column_titles))


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactConditionalFormat:
    """One backend-neutral conditional-format expression."""

    cell_range: str
    formulae: Sequence[str]
    font_color: str | None = None
    fill_color: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "formulae", tuple(self.formulae))


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactWorksheet:
    """Stable observed contents of one artifact worksheet."""

    name: str
    cells: Sequence[ArtifactCell]
    columns: Sequence[ArtifactColumn]
    tables: Sequence[ArtifactTable]
    merged_ranges: Sequence[str] = ()
    freeze_panes: str | None = None
    autofilter: str | None = None
    conditional_formats: Sequence[ArtifactConditionalFormat] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cells", tuple(self.cells))
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "merged_ranges", tuple(self.merged_ranges))
        object.__setattr__(
            self,
            "conditional_formats",
            tuple(self.conditional_formats),
        )

    def cell(self, address: str) -> ArtifactCell:
        """Select an observed cell by A1 address.

        Returns:
            The selected artifact cell.

        Raises:
            LookupError: If the cell was not observed.
        """
        coordinate = parse_cell_address(address)
        canonical = format_cell_address(coordinate.row, coordinate.column)
        for cell in self.cells:
            if cell.address == canonical:
                return cell
        message = f"Cell {canonical!r} was not observed in worksheet {self.name!r}"
        raise LookupError(message)

    @property
    def addresses(self) -> tuple[str, ...]:
        """Observed cell addresses in physical row-major order."""
        return tuple(cell.address for cell in self.cells)

    @property
    def used_range(self) -> str | None:
        """Bounding range of observed cells, if any exist."""
        if not self.cells:
            return None
        coordinates = tuple(parse_cell_address(cell.address) for cell in self.cells)
        start = format_cell_address(
            min(item.row for item in coordinates),
            min(item.column for item in coordinates),
        )
        end = format_cell_address(
            max(item.row for item in coordinates),
            max(item.column for item in coordinates),
        )
        return f"{start}:{end}"

    def column(self, letter: str) -> ArtifactColumn:
        """Select an observed column dimension by letter.

        Returns:
            The selected artifact column.

        Raises:
            LookupError: If the column dimension was not observed.
        """
        coordinate = parse_cell_address(f"{letter}1")
        canonical = format_cell_address(1, coordinate.column)[:-1]
        for column in self.columns:
            if column.letter == canonical:
                return column
        message = f"Column {canonical!r} was not observed in worksheet {self.name!r}"
        raise LookupError(message)

    def table(self, name: str) -> ArtifactTable:
        """Select a native table by name.

        Returns:
            The selected artifact table.

        Raises:
            LookupError: If the table was not observed.
        """
        for table in self.tables:
            if table.name == name:
                return table
        message = f"Table {name!r} was not found in worksheet {self.name!r}"
        raise LookupError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetArtifact:
    """Stable, backend-neutral observation of one spreadsheet artifact."""

    format: str
    worksheets: Sequence[ArtifactWorksheet]

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheets", tuple(self.worksheets))

    def worksheet(self, name: str) -> ArtifactWorksheet:
        """Select an artifact worksheet by name.

        Returns:
            The selected artifact worksheet.

        Raises:
            LookupError: If no worksheet has the requested name.
        """
        for worksheet in self.worksheets:
            if worksheet.name == name:
                return worksheet
        message = f"Worksheet {name!r} was not found"
        raise LookupError(message)


@runtime_checkable
class _BinaryReader(Protocol):
    def read(self, size: int = -1) -> object: ...


@runtime_checkable
class _SeekableBinaryReader(_BinaryReader, Protocol):
    def seek(self, offset: int) -> object: ...

    def tell(self) -> int: ...


ArtifactSource: TypeAlias = (
    RenderResult
    | bytes
    | bytearray
    | memoryview
    | str
    | os.PathLike[str]
    | _BinaryReader
)


def inspect_artifact(
    source: ArtifactSource,
    *,
    format: str | None = None,  # noqa: A002
) -> SpreadsheetArtifact:
    """Inspect an XLSX artifact without exposing backend-native objects.

    Unsupported source objects raise ``TypeError``. An unreadable or malformed
    XLSX package raises ``ArtifactInspectionError`` with source context.

    Returns:
        An immutable observation of workbook contents and presentation.

    Raises:
        ValueError: If the format is unsupported or conflicts with the source.
    """
    payload, declared_format, source_label = _read_source(source)
    resolved_format = _resolve_format(format, declared_format)
    if resolved_format != "xlsx":
        message = f"Unsupported artifact format: {resolved_format!r}"
        raise ValueError(message)
    from ._xlsx import inspect_xlsx  # noqa: PLC0415

    return inspect_xlsx(payload, source=source_label)


def _read_source(
    source: ArtifactSource,
) -> tuple[bytes, str | None, str]:
    if isinstance(source, RenderResult):
        return _read_result(source)
    if isinstance(source, bytes):
        return source, None, "bytes"
    if isinstance(source, (bytearray, memoryview)):
        return bytes(source), None, type(source).__name__
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        return path.read_bytes(), _format_from_path(path), str(path)
    if isinstance(source, _BinaryReader):
        return _read_binary(source), None, type(source).__name__
    message = f"Unsupported artifact source: {type(source).__name__}"
    raise TypeError(message)


def _read_result(source: RenderResult) -> tuple[bytes, str, str]:
    label = f"RenderResult(renderer={source.renderer!r})"
    if source.data is not None:
        return source.data, source.format, label
    if source.target is not None:
        return Path(source.target).read_bytes(), source.format, source.target
    message = "RenderResult contains neither artifact data nor a target path"
    raise ValueError(message)


def _read_binary(source: _BinaryReader) -> bytes:
    position: int | None = None
    if isinstance(source, _SeekableBinaryReader):
        position = source.tell()
        source.seek(0)
    try:
        payload = source.read()
    finally:
        if position is not None and isinstance(source, _SeekableBinaryReader):
            source.seek(position)
    if not isinstance(payload, bytes):
        message = f"Artifact reader returned {type(payload).__name__}, expected bytes"
        raise TypeError(message)
    return payload


def _resolve_format(explicit: str | None, declared: str | None) -> str:
    normalized_explicit = explicit.lower() if explicit is not None else None
    normalized_declared = declared.lower() if declared is not None else None
    if (
        normalized_explicit is not None
        and normalized_declared is not None
        and normalized_explicit != normalized_declared
    ):
        message = (
            f"Explicit artifact format {normalized_explicit!r} conflicts with "
            f"source format {normalized_declared!r}"
        )
        raise ValueError(message)
    return normalized_explicit or normalized_declared or "xlsx"


def _format_from_path(path: Path) -> str | None:
    suffix = path.suffix.lower()
    return suffix[1:] if suffix else None


__all__ = (
    "ArtifactCell",
    "ArtifactColumn",
    "ArtifactConditionalFormat",
    "ArtifactInspectionError",
    "ArtifactSource",
    "ArtifactTable",
    "ArtifactWorksheet",
    "SpreadsheetArtifact",
    "inspect_artifact",
)
