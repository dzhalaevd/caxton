from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Generic, Protocol, TypeAlias, TypeVar, runtime_checkable

from caxton.core.errors import CaxtonTypeError, CaxtonValueError

from ._validation import require_name


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateRef:
    """Logical name of a region inside a template.

    A template reference names a region of the template document, such as
    an XLSX named range. It is deliberately not a
    :class:`~caxton.core.models.expressions.ColumnRef`: a column reference
    names a semantic column of a table, and the two live in different
    namespaces even when they share a spelling.
    """

    name: str

    def __post_init__(self) -> None:
        require_name(self.name, "Template reference name")


TemplateReference: TypeAlias = TemplateRef


@runtime_checkable
class Extension(Protocol):
    """Namespaced capability-aware backend extension envelope."""

    @property
    def namespace(self) -> str: ...

    @property
    def required_capabilities(self) -> frozenset[str]: ...


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateSpecification:
    """Immutable, format-independent description of a template source.

    A path is resolved when the template is inspected for rendering. Raw bytes
    are retained directly in the semantic model.
    """

    source: str | bytes
    format: str
    extensions: Sequence[Extension] = ()

    def __post_init__(self) -> None:
        require_name(self.format, "Template format")
        if not isinstance(self.source, (str, bytes)):
            message = "Template source must be a path or bytes"
            raise CaxtonTypeError(message)
        if isinstance(self.source, str) and not self.source.strip():
            message = "Template source path cannot be empty"
            raise CaxtonValueError(message)
        extensions = tuple(self.extensions)
        for extension in extensions:
            if not isinstance(extension, Extension):
                message = "Template extensions must implement Extension"
                raise CaxtonTypeError(message)
        normalized = (
            bytes(self.source) if isinstance(self.source, bytes) else self.source
        )
        object.__setattr__(self, "source", normalized)
        object.__setattr__(self, "format", self.format.lower().removeprefix("."))
        object.__setattr__(self, "extensions", extensions)


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateRepeat:
    """Generic intent to repeat the region identified by a logical reference."""

    reference: TemplateRef

    def __post_init__(self) -> None:
        if not isinstance(self.reference, TemplateRef):
            message = "Repeat target must be created with slot()"
            raise CaxtonTypeError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateContext:
    """Read-only backend-independent facts discovered from a template."""

    format: str
    source: str
    references: Sequence[str] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "references", tuple(self.references))


@runtime_checkable
class ResolvedTemplateTarget(Protocol):
    """Marker implemented by generic or format-specific resolved targets."""

    @property
    def namespace(self) -> str: ...

    @property
    def reference(self) -> str: ...


IR_co = TypeVar("IR_co", covariant=True)


@dataclasses.dataclass(frozen=True, slots=True)
class TemplateCompilationResult(Generic[IR_co]):
    """Generic renderer input for an inspected and compiled template."""

    document: IR_co
    context: TemplateContext
    targets: Sequence[ResolvedTemplateTarget] = ()
    extensions: Sequence[Extension] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "targets", tuple(self.targets))
        object.__setattr__(self, "extensions", tuple(self.extensions))


__all__ = (
    "Extension",
    "ResolvedTemplateTarget",
    "TemplateCompilationResult",
    "TemplateContext",
    "TemplateRef",
    "TemplateReference",
    "TemplateRepeat",
    "TemplateSpecification",
)
