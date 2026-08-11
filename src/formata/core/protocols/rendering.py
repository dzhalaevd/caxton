from __future__ import annotations

import os
from typing import Protocol, TypeAlias, TypeVar, runtime_checkable

from formata.core.ir.base import DocumentIR
from formata.core.rendering import RenderContext, RendererDescriptor, RenderResult

DocumentIR_contra = TypeVar(
    "DocumentIR_contra",
    bound="DocumentIR",
    contravariant=True,
)


@runtime_checkable
class BinaryWritable(Protocol):
    """External binary buffer whose short writes are completed by adapters."""

    def write(self, data: bytes, /) -> int | None: ...


@runtime_checkable
class BinarySeekable(BinaryWritable, Protocol):
    """Seekable binary stream that can receive an artifact directly."""

    def seek(self, offset: int, whence: int = 0, /) -> int: ...

    def tell(self) -> int: ...

    def flush(self) -> None: ...


OutputTarget: TypeAlias = str | os.PathLike[str] | BinaryWritable


@runtime_checkable
class OutputSink(Protocol):
    """Destination accepting rendered binary chunks or raising on failure."""

    def write(self, data: bytes) -> int: ...


@runtime_checkable
class Renderer(Protocol[DocumentIR_contra]):
    """Backend adapter consuming one compatible family IR."""

    descriptor: RendererDescriptor

    def render(
        self,
        document: DocumentIR_contra,
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult: ...


__all__ = (
    "BinarySeekable",
    "BinaryWritable",
    "OutputSink",
    "OutputTarget",
    "Renderer",
)
