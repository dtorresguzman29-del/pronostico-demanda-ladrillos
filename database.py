from __future__ import annotations

import os

import pandas as pd
import psycopg

from forecasting import SALES_COLUMN, YEAR_COLUMN, normalize_sales_data

_TABLE = "public.brick_sales"
_EMPTY_HISTORY = pd.DataFrame(columns=[YEAR_COLUMN, SALES_COLUMN])


def _ensure_schema(connection: psycopg.Connection) -> None:
    """Create the sales table on first use; safe to call on every connection."""
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            year INTEGER PRIMARY KEY,
            quantity DOUBLE PRECISION NOT NULL CHECK (quantity >= 0),
            is_example BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )


def _database_url() -> str:
    """Read DATABASE_URL from the host environment or Streamlit secrets."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    try:
        import streamlit as st

        database_url = st.secrets.get("DATABASE_URL")
    except Exception:
        database_url = None

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL no está configurada. Añádela en los secretos de "
            "Streamlit o como variable de entorno del servidor."
        )
    return str(database_url)


def _connect() -> psycopg.Connection:
    return psycopg.connect(_database_url())


def load_sales_records() -> tuple[pd.DataFrame, bool]:
    """Load the saved annual sales and report whether they are example records."""
    with _connect() as connection:
        _ensure_schema(connection)
        rows = connection.execute(
            f"SELECT year, quantity, is_example FROM {_TABLE} ORDER BY year"
        ).fetchall()

    if not rows:
        return _EMPTY_HISTORY.copy(), False

    records = pd.DataFrame(
        {
            YEAR_COLUMN: [int(row[0]) for row in rows],
            SALES_COLUMN: [float(row[1]) for row in rows],
        }
    )
    return records, all(bool(row[2]) for row in rows)


def save_sales_records(data: pd.DataFrame, *, is_example: bool = False) -> None:
    """Atomically synchronize the saved records with the submitted history."""
    records, errors = normalize_sales_data(data)
    if errors:
        raise ValueError(" ".join(errors))
    if records.empty:
        raise ValueError("Conserva al menos un registro de ventas.")

    incoming = {
        int(row[YEAR_COLUMN]): (float(row[SALES_COLUMN]), bool(is_example))
        for _, row in records.iterrows()
    }

    with _connect() as connection:
        _ensure_schema(connection)
        current_rows = connection.execute(
            f"SELECT year, quantity, is_example FROM {_TABLE}"
        ).fetchall()
        current = {
            int(year): (float(quantity), bool(example))
            for year, quantity, example in current_rows
        }

        years_to_delete = sorted(set(current) - set(incoming))
        if years_to_delete:
            connection.execute(
                f"DELETE FROM {_TABLE} WHERE year = ANY(%s)",
                (years_to_delete,),
            )

        rows_to_save = [
            (year, quantity, example)
            for year, (quantity, example) in incoming.items()
            if current.get(year) != (quantity, example)
        ]
        if rows_to_save:
            with connection.cursor() as cursor:
                cursor.executemany(
                    f"""
                    INSERT INTO {_TABLE} (year, quantity, is_example)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (year)
                    DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        is_example = EXCLUDED.is_example
                    """,
                    rows_to_save,
                )
