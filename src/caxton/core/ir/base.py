from __future__ import annotations

from typing import Protocol, runtime_checkable

from caxton.core.models.common import DocumentKind, DocumentMetadata


@runtime_checkable
class DocumentIR(Protocol):
    """Common read-only envelope implemented by every versioned family IR."""

    @property
    def version(self) -> int: ...

    @property
    def kind(self) -> DocumentKind: ...

    @property
    def metadata(self) -> DocumentMetadata: ...


__all__ = ("DocumentIR",)
