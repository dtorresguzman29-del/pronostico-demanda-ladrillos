from __future__ import annotations

import unicodedata
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import Holt

YEAR_COLUMN = "Año"
SALES_COLUMN = "Ventas (ladrillos)"

_YEAR_HEADERS = {"ano", "anio", "year", "periodo"}
_SALES_HEADERS = {
    "cantidad",
    "cantidaddeladrillos",
    "cantidadladrillos",
    "ladrillos",
    "sales",
    "ventas",
    "ventasladrillos",
    "unidades",
}


@dataclass(frozen=True)
class ForecastResult:
    history: pd.DataFrame
    forecast_year: int
    forecast_units: float
    alpha: float
    results_table: pd.DataFrame


def _normalize_header(header: object) -> str:
    decomposed = unicodedata.normalize("NFKD", str(header).strip().lower())
    without_accents = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    return "".join(
        character for character in without_accents if character.isalnum()
    )


def normalize_sales_data(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Validate and standardize annual sales records."""
    if not isinstance(data, pd.DataFrame):
        return pd.DataFrame(columns=[YEAR_COLUMN, SALES_COLUMN]), [
            "Los datos deben tener formato de tabla."
        ]

    headers = {_normalize_header(column): column for column in data.columns}
    year_header = next(
        (headers[name] for name in _YEAR_HEADERS if name in headers), None
    )
    sales_header = next(
        (headers[name] for name in _SALES_HEADERS if name in headers), None
    )

    missing_columns = []
    if year_header is None:
        missing_columns.append("Año")
    if sales_header is None:
        missing_columns.append("Ventas (ladrillos)")
    if missing_columns:
        return pd.DataFrame(columns=[YEAR_COLUMN, SALES_COLUMN]), [
            "No se encontraron las columnas requeridas: "
            + " y ".join(missing_columns) + "."
        ]

    records = data[[year_header, sales_header]].copy()
    records.columns = [YEAR_COLUMN, SALES_COLUMN]
    records = records.replace(r"^\s*$", pd.NA, regex=True)
    records = records.loc[~records.isna().all(axis=1)].copy()

    if records.empty:
        return pd.DataFrame(columns=[YEAR_COLUMN, SALES_COLUMN]), []

    year_values = pd.to_numeric(records[YEAR_COLUMN], errors="coerce")
    sales_values = pd.to_numeric(records[SALES_COLUMN], errors="coerce")

    year_array = year_values.to_numpy(dtype=float, na_value=np.nan)
    sales_array = sales_values.to_numpy(dtype=float, na_value=np.nan)

    valid_year = (
        np.isfinite(year_array)
        & (year_array >= 1)
        & (year_array <= 9999)
        & (year_array == np.floor(year_array))
    )
    valid_sales = np.isfinite(sales_array) & (sales_array >= 0)

    errors = []
    if not valid_year.all():
        errors.append("Cada registro debe tener un año entero válido.")
    if not valid_sales.all():
        errors.append(
            "Cada registro debe tener una cantidad numérica igual o mayor que cero."
        )
    if errors:
        return pd.DataFrame(columns=[YEAR_COLUMN, SALES_COLUMN]), errors

    normalized = pd.DataFrame({
        YEAR_COLUMN: year_array.astype(int),
        SALES_COLUMN: sales_array.astype(float),
    })

    duplicates = normalized.loc[
        normalized[YEAR_COLUMN].duplicated(keep=False), YEAR_COLUMN
    ].unique()
    if len(duplicates):
        duplicate_years = ", ".join(str(year) for year in sorted(duplicates))
        return pd.DataFrame(columns=[YEAR_COLUMN, SALES_COLUMN]), [
            f"Hay años repetidos: {duplicate_years}. "
            "Debe existir un solo registro por año."
        ]

    return normalized.sort_values(YEAR_COLUMN).reset_index(drop=True), []


def validate_history(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Validate annual records and consecutive year spacing."""
    history, errors = normalize_sales_data(data)
    if errors:
        return history, errors
    if len(history) < 2:
        return history, ["Ingresa al menos dos años de ventas."]

    years = history[YEAR_COLUMN].to_numpy(dtype=int)
    missing_years = sorted(set(range(years[0], years[-1] + 1)) - set(years))
    if missing_years:
        visible_years = ", ".join(str(year) for year in missing_years[:8])
        suffix = "…" if len(missing_years) > 8 else ""
        return history, [
            f"Faltan años intermedios ({visible_years}{suffix}). "
            "Debe existir un registro por cada año."
        ]

    return history, []


def incomplete_current_years(
    data: pd.DataFrame, current_year: int | None = None
) -> list[int]:
    """Kept for compatibility; the latest year is no longer excluded."""
    return []


def sales_records_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Compare sales records independent of integer/float dtypes."""
    normalized_left, left_errors = normalize_sales_data(left)
    normalized_right, right_errors = normalize_sales_data(right)

    if left_errors or right_errors or len(normalized_left) != len(normalized_right):
        return False

    return bool(
        np.array_equal(
            normalized_left[YEAR_COLUMN].to_numpy(dtype=int),
            normalized_right[YEAR_COLUMN].to_numpy(dtype=int),
        )
        and np.allclose(
            normalized_left[SALES_COLUMN].to_numpy(dtype=float),
            normalized_right[SALES_COLUMN].to_numpy(dtype=float),
            rtol=0,
            atol=1e-9,
        )
    )


def forecast_simple_exponential_smoothing(
    data: pd.DataFrame,
    alpha: float,
    target_year: int | None = None,
) -> ForecastResult:
    """Forecast with damped Holt trend using every entered year."""
    history, errors = validate_history(data)
    if errors:
        raise ValueError(" ".join(errors))

    if not np.isfinite(alpha) or not 0 < alpha <= 1:
        raise ValueError("Alfa debe ser mayor que 0 y menor o igual que 1.")

    years = history[YEAR_COLUMN].to_numpy(dtype=int)
    last_historical_year = int(years[-1])
    forecast_year = (
        last_historical_year + 1 if target_year is None else target_year
    )

    if (
        isinstance(forecast_year, bool)
        or not isinstance(forecast_year, (int, np.integer))
        or forecast_year <= last_historical_year
        or forecast_year > 9999
    ):
        raise ValueError(
            "El año objetivo debe ser posterior al último año ingresado "
            "y no puede superar 9999."
        )

    horizon = int(forecast_year - last_historical_year)
    values = history[SALES_COLUMN].to_numpy(dtype=float)
    series = pd.Series(values, dtype=float)

    try:
        model = Holt(
            series,
            damped_trend=True,
            initialization_method="estimated",
        )
        fitted_model = model.fit(
            smoothing_level=float(alpha),
            optimized=True,
        )
        forecast_path = np.asarray(
            fitted_model.forecast(horizon), dtype=float
        )
        fitted_values = np.asarray(
            fitted_model.fittedvalues, dtype=float
        )
    except Exception as error:
        raise RuntimeError(
            "No se pudo ajustar el modelo de tendencia con estos datos. "
            "Revisa las cantidades y vuelve a intentarlo."
        ) from error

    if (
        len(forecast_path) != horizon
        or not np.isfinite(forecast_path).all()
        or not np.isfinite(fitted_values).all()
    ):
        raise RuntimeError("El modelo produjo resultados no válidos.")

    # Sales forecasts cannot be negative.
    forecast_path = np.maximum(forecast_path, 0)
    fitted_values = np.maximum(fitted_values, 0)

    one_step_forecasts = [
        None,
        *fitted_values[1:].tolist(),
    ]

    forecast_years = list(
        range(last_historical_year + 1, int(forecast_year) + 1)
    )

    results_table = pd.DataFrame({
        "Año": [*years.tolist(), *forecast_years],
        "Tipo": ["Histórico"] * len(history)
        + ["Pronóstico"] * horizon,
        "Ventas reales (ladrillos)": [
            *values.tolist(), *([None] * horizon)
        ],
        "Pronóstico del modelo (ladrillos)": [
            *one_step_forecasts, *forecast_path.tolist()
        ],
    })

    return ForecastResult(
        history=history,
        forecast_year=int(forecast_year),
        forecast_units=float(forecast_path[-1]),
        alpha=float(alpha),
        results_table=results_table,
    )
