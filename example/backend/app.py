from __future__ import annotations

import contextlib
import datetime as dt
import sqlite3
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from formata import (
    boolean,
    date,
    decimal,
    integer,
    path,
    ref,
    render,
    sheet,
    spreadsheet,
    table,
    text,
)
from formata.core.models import SpreadsheetDocument

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DATABASE_PATH = Path(__file__).with_name("stations.sqlite3")


@dataclass(frozen=True, slots=True)
class Owner:
    """Nested domain value used to demonstrate explicit path access."""

    name: str


@dataclass(frozen=True, slots=True)
class Station:
    """Repository DTO consumed by Formata without a framework adapter."""

    id: int
    emis_code: str
    comment: str
    incident_number: str
    days_on_base_price: int
    owner: Owner
    price: Decimal
    base_price: Decimal
    active: bool
    created_on: dt.date


class StationCreate(BaseModel):
    """HTTP input validated independently from the report model."""

    emis_code: str = Field(min_length=1)
    comment: str = Field(min_length=1)
    incident_number: str = Field(min_length=1)
    days_on_base_price: int = Field(ge=0)
    owner: str = Field(min_length=1)
    price: Decimal
    base_price: Decimal
    active: bool = True


class StationRepository:
    """Small SQLite boundary yielding lazy dataclass rows."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        """Create storage needed by the example service."""
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS stations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    emis_code TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    incident_number TEXT NOT NULL,
                    days_on_base_price INTEGER NOT NULL,
                    owner TEXT NOT NULL,
                    price TEXT NOT NULL,
                    base_price TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    created_on TEXT NOT NULL
                )
                """,
            )

    def add(self, payload: StationCreate) -> int:
        """Persist a validated request and return its identifier.

        Returns:
            The generated database identifier.
        """
        values = (
            payload.emis_code,
            payload.comment,
            payload.incident_number,
            payload.days_on_base_price,
            payload.owner,
            str(payload.price),
            str(payload.base_price),
            int(payload.active),
            dt.datetime.now(tz=dt.UTC).date().isoformat(),
        )
        with sqlite3.connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO stations (
                    emis_code, comment, incident_number, days_on_base_price,
                    owner, price, base_price, active, created_on
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return int(cursor.lastrowid)

    def iter_stations(self) -> Iterator[Station]:
        """Yield one-shot rows so the renderer can select a streaming plan."""
        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            records = connection.execute("SELECT * FROM stations ORDER BY id")
            for record in records:
                yield Station(
                    id=record["id"],
                    emis_code=record["emis_code"],
                    comment=record["comment"],
                    incident_number=record["incident_number"],
                    days_on_base_price=record["days_on_base_price"],
                    owner=Owner(record["owner"]),
                    price=Decimal(record["price"]),
                    base_price=Decimal(record["base_price"]),
                    active=bool(record["active"]),
                    created_on=dt.date.fromisoformat(record["created_on"]),
                )


def build_report(rows: object) -> SpreadsheetDocument:
    """Map repository DTOs into one backend-independent report.

    Returns:
        An immutable spreadsheet specification.
    """
    return spreadsheet(
        sheet(
            "Stations",
            table(
                rows,
                integer("id").titled("ID"),
                text("emis", source="emis_code").titled("EMIS"),
                text("comment").titled("Comment"),
                text("incident", source="incident_number").titled("Incident"),
                integer("days", source="days_on_base_price").titled("Days"),
                text("owner", source=path("owner", "name")).titled("Owner"),
                decimal("price").titled("Price"),
                decimal("base_price").titled("Base price"),
                decimal("delta", source=ref("price") - ref("base_price")).titled(
                    "Delta"
                ),
                boolean("active").titled("Active"),
                date("created_on").titled("Created"),
            ),
        ),
    )


repository = StationRepository(DATABASE_PATH)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the local database when FastAPI starts."""
    repository.initialize()
    yield


app = FastAPI(title="Formata backend example", lifespan=lifespan)


@app.post("/stations", status_code=status.HTTP_201_CREATED)
def create_station(payload: StationCreate) -> dict[str, int]:
    """Store one station accepted through a Pydantic model.

    Returns:
        The generated station identifier.
    """
    return {"id": repository.add(payload)}


@app.get("/reports/stations.xlsx")
def station_report() -> Response:
    """Stream database rows into XLSX and return the completed artifact.

    Returns:
        A downloadable XLSX response.

    Raises:
        RuntimeError: If memory rendering unexpectedly returns no payload.
    """
    document = build_report(repository.iter_stations())
    result = render(document, mode="stream")
    if result.data is None:
        message = "Memory rendering did not return XLSX bytes"
        raise RuntimeError(message)
    return Response(
        content=result.data,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="stations.xlsx"'},
    )
