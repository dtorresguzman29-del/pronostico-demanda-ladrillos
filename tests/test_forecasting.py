import pandas as pd
import pytest

from forecasting import (
    SALES_COLUMN,
    YEAR_COLUMN,
    forecast_simple_exponential_smoothing,
    incomplete_current_years,
    normalize_sales_data,
    sales_records_equal,
    validate_history,
)


def test_forecast_uses_simple_exponential_smoothing() -> None:
    data = pd.DataFrame(
        {
            YEAR_COLUMN: [2020, 2021, 2022],
            SALES_COLUMN: [100, 200, 300],
        }
    )

    result = forecast_simple_exponential_smoothing(data, alpha=0.5)

    assert result.forecast_year == 2023
    assert result.forecast_units == pytest.approx(225)
    assert result.results_table["Nivel suavizado (ladrillos)"].iloc[:3].tolist() == (
        pytest.approx([100, 150, 225])
    )
    one_step = result.results_table["Pronóstico a un paso (ladrillos)"].iloc[:3]
    assert pd.isna(one_step.iloc[0])
    assert one_step.iloc[1:].tolist() == pytest.approx([100, 150])
    assert result.results_table["Tipo"].iloc[-1] == "Pronóstico"


def test_forecast_repeats_last_ses_level_for_multiple_steps() -> None:
    data = pd.DataFrame(
        {
            YEAR_COLUMN: [2020, 2021, 2022],
            SALES_COLUMN: [100, 200, 300],
        }
    )

    result = forecast_simple_exponential_smoothing(
        data, alpha=0.5, target_year=2025
    )

    assert result.forecast_year == 2025
    assert result.forecast_units == pytest.approx(225)
    assert result.results_table[YEAR_COLUMN].tolist() == [
        2020, 2021, 2022, 2023, 2024, 2025
    ]
    assert result.results_table["Pronóstico a un paso (ladrillos)"].iloc[-3:].tolist() == (
        pytest.approx([225, 225, 225])
    )


def test_forecast_rejects_target_year_not_after_history() -> None:
    data = pd.DataFrame(
        {YEAR_COLUMN: [2020, 2021], SALES_COLUMN: [100, 200]}
    )

    with pytest.raises(ValueError, match="posterior"):
        forecast_simple_exponential_smoothing(data, alpha=0.5, target_year=2021)


def test_incomplete_current_year_is_detected_for_exclusion() -> None:
    data = pd.DataFrame(
        {YEAR_COLUMN: [2024, 2025, 2026], SALES_COLUMN: [100, 200, 30]}
    )

    assert incomplete_current_years(data, current_year=2026) == [2026]
    assert incomplete_current_years(data, current_year=2027) == []


def test_normalize_sales_data_accepts_spanish_csv_headers_and_sorts_years() -> None:
    data = pd.DataFrame(
        {
            "año": [2022, 2020, 2021],
            "cantidad de ladrillos": [300, 100, 200],
        }
    )

    normalized, errors = normalize_sales_data(data)

    assert errors == []
    assert normalized[YEAR_COLUMN].tolist() == [2020, 2021, 2022]
    assert normalized[SALES_COLUMN].tolist() == [100, 200, 300]


def test_validate_history_rejects_duplicate_years() -> None:
    data = pd.DataFrame(
        {
            "Año": [2020, 2020],
            "Ventas (ladrillos)": [100, 120],
        }
    )

    _, errors = validate_history(data)

    assert any("repetidos" in error for error in errors)


def test_validate_history_requires_consecutive_years() -> None:
    data = pd.DataFrame(
        {
            "Año": [2020, 2022],
            "Ventas (ladrillos)": [100, 300],
        }
    )

    _, errors = validate_history(data)

    assert any("Faltan años intermedios" in error for error in errors)


def test_forecast_rejects_alpha_outside_allowed_range() -> None:
    data = pd.DataFrame(
        {
            "Año": [2020, 2021],
            "Ventas (ladrillos)": [100, 200],
        }
    )

    with pytest.raises(ValueError, match="Alfa"):
        forecast_simple_exponential_smoothing(data, alpha=0)


def test_sales_records_equal_ignores_integer_or_float_column_types() -> None:
    left = pd.DataFrame({"Año": [2020, 2021], "Ventas (ladrillos)": [100, 200]})
    right = pd.DataFrame(
        {"Año": [2020.0, 2021.0], "Ventas (ladrillos)": [100.0, 200.0]}
    )

    assert sales_records_equal(left, right)



def test_incomplete_2026_is_excluded_from_annual_forecast() -> None:
    data = pd.DataFrame(
        {
            YEAR_COLUMN: [2023, 2024, 2025, 2026],
            SALES_COLUMN: [100, 200, 300, 25],
        }
    )

    incomplete = incomplete_current_years(data, current_year=2026)
    complete_history = data.loc[~data[YEAR_COLUMN].isin(incomplete)]
    result = forecast_simple_exponential_smoothing(complete_history, alpha=0.5)

    assert incomplete == [2026]
    assert result.forecast_year == 2026
    assert result.forecast_units == pytest.approx(225)


def test_alpha_one_uses_latest_complete_observation() -> None:
    data = pd.DataFrame(
        {YEAR_COLUMN: [2022, 2023, 2024], SALES_COLUMN: [100, 250, 400]}
    )

    result = forecast_simple_exponential_smoothing(data, alpha=1.0)

    assert result.forecast_units == pytest.approx(400)


def test_normalize_rejects_missing_or_non_finite_values() -> None:
    data = pd.DataFrame(
        {YEAR_COLUMN: [2020, 2021], SALES_COLUMN: [100, float("inf")]}
    )

    normalized, errors = normalize_sales_data(data)

    assert normalized.empty
    assert any("cantidad numérica" in error for error in errors)


def test_normalize_ignores_fully_empty_rows_but_rejects_partial_rows() -> None:
    valid = pd.DataFrame(
        {
            YEAR_COLUMN: [2020, None],
            SALES_COLUMN: [100, None],
        }
    )
    normalized, errors = normalize_sales_data(valid)
    assert errors == []
    assert normalized[YEAR_COLUMN].tolist() == [2020]

    partial = pd.DataFrame(
        {
            YEAR_COLUMN: [2020, 2021],
            SALES_COLUMN: [100, None],
        }
    )
    _, errors = normalize_sales_data(partial)
    assert any("cantidad numérica" in error for error in errors)
