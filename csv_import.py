from __future__ import annotations

from io import BytesIO, StringIO

import pandas as pd


def read_sales_csv(file_content: bytes) -> pd.DataFrame:
    """Read CSV files exported from Excel using common encodings and separators."""
    if not isinstance(file_content, bytes):
        raise ValueError("El archivo CSV debe recibirse como contenido binario.")

    if not file_content:
        raise ValueError("El archivo CSV está vacío.")

    encodings = ("utf-8-sig", "cp1252", "latin1")
    separators = (None, ";", ",")

    last_error = None

    for encoding in encodings:
        try:
            text = file_content.decode(encoding)
        except UnicodeDecodeError as error:
            last_error = error
            continue

        for separator in separators:
            try:
                if separator is None:
                    data = pd.read_csv(
                        StringIO(text),
                        sep=None,
                        engine="python",
                    )
                else:
                    data = pd.read_csv(
                        StringIO(text),
                        sep=separator,
                    )

                if len(data.columns) >= 2:
                    return data

            except (pd.errors.ParserError, UnicodeDecodeError) as error:
                last_error = error

    try:
        return pd.read_csv(BytesIO(file_content), encoding="latin1", sep=";")
    except Exception as error:
        raise ValueError(
            "No se pudo interpretar el CSV. Comprueba que tenga las columnas "
            "Año y Ventas (ladrillos)."
        ) from (last_error or error)
