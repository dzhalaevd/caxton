from __future__ import annotations

import dataclasses
import posixpath
import zipfile
from collections.abc import Iterable, Sequence
from io import BytesIO
from pathlib import PurePosixPath
from typing import Protocol

from openpyxl.xml.functions import fromstring, tostring

from caxton.core.errors import InvalidTemplateRefError, TemplateError

_RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
_SPREADSHEET_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


@dataclasses.dataclass(frozen=True, slots=True)
class PivotDescriptor:
    """Resolved XLSX package locations for one existing pivot."""

    name: str
    definition_part: str
    cache_definition_part: str | None


@dataclasses.dataclass(slots=True)
class XlsxPackage:
    """Backend-local seekable XLSX/ZIP package abstraction."""

    _parts: dict[str, bytes]
    _order: list[str]

    @classmethod
    def from_bytes(cls, payload: bytes) -> XlsxPackage:
        """Open an XLSX payload as independently mutable package parts.

        Returns:
            A seekable package copy.

        Raises:
            TemplateError: If the payload is not a readable ZIP package.
        """
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                order = archive.namelist()
                parts = {name: archive.read(name) for name in order}
        except (OSError, zipfile.BadZipFile) as error:
            message = "Could not open the rendered XLSX package"
            raise TemplateError(message) from error
        return cls(parts, order)

    @property
    def part_names(self) -> tuple[str, ...]:
        return tuple(self._order)

    def read(self, name: str) -> bytes:
        try:
            return self._parts[name]
        except KeyError as error:
            message = f"XLSX package part {name!r} was not found"
            raise InvalidTemplateRefError(message) from error

    def write(self, name: str, payload: bytes) -> None:
        if name not in self._parts:
            self._order.append(name)
        self._parts[name] = bytes(payload)

    def copy_parts_from(
        self,
        source: XlsxPackage,
        names: Iterable[str],
    ) -> None:
        for name in names:
            self.write(name, source.read(name))

    def to_bytes(self) -> bytes:
        """Serialize the current package deterministically.

        Returns:
            The complete XLSX package payload.
        """
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in self._order:
                archive.writestr(name, self._parts[name])
        return buffer.getvalue()


class XlsxPackagePostProcessor(Protocol):
    """Backend-local package mutation performed after workbook rendering."""

    def process(self, package: XlsxPackage) -> None: ...


@dataclasses.dataclass(frozen=True, slots=True)
class PivotPatch:
    descriptor: PivotDescriptor
    sheet: str
    cell_range: str
    refresh_on_open: bool


@dataclasses.dataclass(frozen=True, slots=True)
class PivotPostProcessor:
    """Restore pivot parts and patch cache bindings without public XML paths."""

    source: XlsxPackage
    patches: Sequence[PivotPatch]

    def process(self, package: XlsxPackage) -> None:
        package.copy_parts_from(
            self.source,
            (name for name in self.source.part_names if _is_pivot_part(name)),
        )
        for patch in self.patches:
            cache_part = patch.descriptor.cache_definition_part
            if cache_part is None:
                message = f"Pivot {patch.descriptor.name!r} has no cache definition"
                raise InvalidTemplateRefError(message)
            root = fromstring(package.read(cache_part))
            enabled = "1" if patch.refresh_on_open else "0"
            root.set("refreshOnLoad", enabled)
            root.set("enableRefresh", enabled)
            worksheet_source = root.find(
                f".//{{{_SPREADSHEET_NAMESPACE}}}worksheetSource",
            )
            if worksheet_source is None:
                message = f"Pivot {patch.descriptor.name!r} has no worksheet source"
                raise InvalidTemplateRefError(message)
            worksheet_source.set("sheet", patch.sheet)
            worksheet_source.set("ref", patch.cell_range.replace("$", ""))
            serialized = tostring(root, xml_declaration=True)
            package.write(
                cache_part,
                serialized.encode() if isinstance(serialized, str) else serialized,
            )


def inspect_pivots(payload: bytes) -> tuple[PivotDescriptor, ...]:
    """Resolve pivot names to backend-local package descriptors.

    Returns:
        Pivot descriptors discovered from package relationships.
    """
    package = XlsxPackage.from_bytes(payload)
    output: list[PivotDescriptor] = []
    for part in package.part_names:
        if not _is_pivot_definition(part):
            continue
        root = fromstring(package.read(part))
        name = root.get("name")
        if name is None:
            continue
        output.append(
            PivotDescriptor(
                name=name,
                definition_part=part,
                cache_definition_part=_pivot_cache_part(package, part),
            ),
        )
    return tuple(output)


def run_postprocessors(
    payload: bytes,
    processors: Sequence[XlsxPackagePostProcessor],
) -> bytes:
    """Apply post-processors in declaration order to one seekable package.

    Returns:
        The post-processed XLSX payload.
    """
    if not processors:
        return payload
    package = XlsxPackage.from_bytes(payload)
    for processor in processors:
        processor.process(package)
    return package.to_bytes()


def _pivot_cache_part(package: XlsxPackage, pivot_part: str) -> str | None:
    path = PurePosixPath(pivot_part)
    relationships = str(path.parent / "_rels" / f"{path.name}.rels")
    if relationships not in package.part_names:
        return None
    root = fromstring(package.read(relationships))
    for relationship in root.findall(f"{{{_RELATIONSHIP_NAMESPACE}}}Relationship"):
        if str(relationship.get("Type", "")).endswith("/pivotCacheDefinition"):
            target = relationship.get("Target")
            if target is not None:
                return posixpath.normpath(posixpath.join(str(path.parent), target))
    return None


def _is_pivot_definition(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        str(path.parent) == "xl/pivotTables"
        and path.name.startswith("pivotTable")
        and path.suffix == ".xml"
    )


def _is_pivot_part(name: str) -> bool:
    return name.startswith(
        (
            "xl/pivotTables/",
            "xl/pivotCache/",
        ),
    )


__all__ = (
    "PivotDescriptor",
    "PivotPatch",
    "PivotPostProcessor",
    "XlsxPackage",
    "XlsxPackagePostProcessor",
    "inspect_pivots",
    "run_postprocessors",
)
