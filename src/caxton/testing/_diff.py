from __future__ import annotations

import dataclasses

from caxton.core._compat import StrEnum
from caxton.core._values import freeze_value


class DifferenceKind(StrEnum):
    """Kind of observable mismatch between two inspected values."""

    VALUE = "value"
    ORDER = "order"
    MISSING = "missing"
    UNEXPECTED = "unexpected"


@dataclasses.dataclass(frozen=True, slots=True)
class Difference:
    """One stable, path-addressed mismatch between expected and actual values."""

    path: str
    kind: DifferenceKind
    expected: object
    actual: object

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expected",
            freeze_value(self.expected, label="Difference expected value"),
        )
        object.__setattr__(
            self,
            "actual",
            freeze_value(self.actual, label="Difference actual value"),
        )


__all__ = ("Difference", "DifferenceKind")
