from __future__ import annotations

import enum
import sys

if sys.version_info >= (3, 11):
    from typing import Self

    StrEnum = enum.StrEnum
else:
    from typing_extensions import Self

    class StrEnum(str, enum.Enum):
        """Python 3.10-compatible subset of :class:`enum.StrEnum`."""

        __str__ = str.__str__


__all__ = ("Self", "StrEnum")
