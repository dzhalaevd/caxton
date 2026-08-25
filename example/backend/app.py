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

from caxton import (
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
from caxton.core.models import SpreadsheetDocument

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DATABASE_PATH = Path(__file__).with_name("products.sqlite3")


@dataclass(frozen=True, slots=True)
class Supplier:
    """Nested domain value used to demonstrate explicit path access."""

    name: str


@dataclass(frozen=True, slots=True)
class Product:
    """Repository DTO consumed by Caxton without a framework adapter."""

    id: int
    sku: str
    description: str
    reference: str
    days_in_stock: int
    supplier: Supplier
    price: Decimal
    list_price: Decimal
    in_stock: bool
    added_on: dt.date


class ProductCreate(BaseModel):
    """HTTP input validated independently from the report model."""

    sku: str = Field(min_length=1)
    description: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    days_in_stock: int = Field(ge=0)
    supplier: str = Field(min_length=1)
    price: Decimal
    list_price: Decimal
    in_stock: bool = True


class ProductRepository:
    """Small SQLite boundary yielding lazy dataclass rows."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        """Create storage needed by the example service."""
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reference TEXT NOT NULL,
                    days_in_stock INTEGER NOT NULL,
                    supplier TEXT NOT NULL,
                    price TEXT NOT NULL,
                    list_price TEXT NOT NULL,
                    in_stock INTEGER NOT NULL,
                    added_on TEXT NOT NULL
                )
                """,
            )

    def add(self, payload: ProductCreate) -> int:
        """Persist a validated request and return its identifier.

        Returns:
            The generated database identifier.
        """
        values = (
            payload.sku,
            payload.description,
            payload.reference,
            payload.days_in_stock,
            payload.supplier,
            str(payload.price),
            str(payload.list_price),
            int(payload.in_stock),
            dt.datetime.now(tz=dt.UTC).date().isoformat(),
        )
        with sqlite3.connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO products (
                    sku, description, reference, days_in_stock,
                    supplier, price, list_price, in_stock, added_on
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return int(cursor.lastrowid)

    def iter_products(self) -> Iterator[Product]:
        """Yield one-shot rows so the renderer can select a streaming plan."""
        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            records = connection.execute("SELECT * FROM products ORDER BY id")
            for record in records:
                yield Product(
                    id=record["id"],
                    sku=record["sku"],
                    description=record["description"],
                    reference=record["reference"],
                    days_in_stock=record["days_in_stock"],
                    supplier=Supplier(record["supplier"]),
                    price=Decimal(record["price"]),
                    list_price=Decimal(record["list_price"]),
                    in_stock=bool(record["in_stock"]),
                    added_on=dt.date.fromisoformat(record["added_on"]),
                )


def build_report(rows: object) -> SpreadsheetDocument:
    """Map repository DTOs into one backend-independent report.

    Returns:
        An immutable spreadsheet specification.
    """
    return spreadsheet(
        sheet(
            "Products",
            table(
                rows,
                integer("id").titled("ID"),
                text("sku").titled("SKU"),
                text("description").titled("Description"),
                text("reference").titled("Reference"),
                integer("days", source="days_in_stock").titled("Days in stock"),
                text("supplier", source=path("supplier", "name")).titled("Supplier"),
                decimal("price").titled("Price"),
                decimal("list_price").titled("List price"),
                decimal("delta", source=ref("price") - ref("list_price")).titled(
                    "Delta"
                ),
                boolean("in_stock").titled("In stock"),
                date("added_on").titled("Added"),
            ),
        ),
    )


repository = ProductRepository(DATABASE_PATH)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the local database when FastAPI starts."""
    repository.initialize()
    yield


app = FastAPI(title="Caxton backend example", lifespan=lifespan)


@app.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate) -> dict[str, int]:
    """Store one product accepted through a Pydantic model.

    Returns:
        The generated product identifier.
    """
    return {"id": repository.add(payload)}


@app.get("/reports/products.xlsx")
def product_report() -> Response:
    """Stream database rows into XLSX and return the completed artifact.

    Returns:
        A downloadable XLSX response.

    Raises:
        RuntimeError: If memory rendering unexpectedly returns no payload.
    """
    document = build_report(repository.iter_products())
    result = render(document, mode="stream")
    if result.data is None:
        message = "Memory rendering did not return XLSX bytes"
        raise RuntimeError(message)
    return Response(
        content=result.data,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="products.xlsx"'},
    )
