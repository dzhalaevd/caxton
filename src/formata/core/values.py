from __future__ import annotations

import datetime as dt
import decimal
from typing import TypeAlias

CellValue: TypeAlias = (
    bool
    | bytes
    | dt.date
    | dt.datetime
    | dt.time
    | dt.timedelta
    | decimal.Decimal
    | float
    | int
    | str
    | None
)


__all__ = ("CellValue",)
