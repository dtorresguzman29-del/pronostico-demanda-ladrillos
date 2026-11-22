from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import load_sales_records, save_sales_records
from csv_import import read_sales_csv
from forecasting import (
    SALES_COLUMN,
    YEAR_COLUMN,
    forecast_simple_exponential_smoothing,
    normalize_sales_data,
    sales_records_equal,
    validate_history,
)

APP_DIR = Path(__file__).resolve().parent
SAMPLE_DATA_PATH = APP_DIR / "sample_data.csv"
SAMPLE_DATA = pd.read_csv(SAMPLE_DATA_PATH)
CSV_TEMPLATE = pd.DataFrame(columns=[YEAR_COLUMN, SALES_COLUMN]).to_csv(index=False)


def format_bricks(value: float | int) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


st.set_page_config(
    page_title="Pronóstico de demanda de ladrillos",
    layout="wide",
)

if "sales_data" not in st.session_state or "persisted_data" not in st.session_state:
    try:
        stored_data, stored_data_is_example = load_sales_records()
    except Exception as error:
        st.error(
            "No se pudo conectar con PostgreSQL. Comprueba que DATABASE_URL "
            "esté configurada correctamente y que la base de datos permita "
            "conexiones SSL. Detalle técnico: " + str(error)
        )
        st.stop()

    if "sales_data" not in st.session_state:
        st.session_state.sales_data = (
            stored_data.copy() if not stored_data.empty else SAMPLE_DATA.copy()
        )
    if "persisted_data" not in st.session_state:
        st.session_state.persisted_data = stored_data.copy()
    if "is_sample_data" not in st.session_state:
        st.session_state.is_sample_data = stored_data_is_example or stored_data.empty

if "data_revision" not in st.session_state:
    st.session_state.data_revision = 0
if "is_sample_data" not in st.session_state:
    st.session_state.is_sample_data = False
if "csv_feedback" not in st.session_state:
    st.session_state.csv_feedback = None

st.title("Pronóstico de demanda de ladrillos")
st.caption(
    "Ingresa tus ventas históricas y obtén una estimación para el año siguiente, "
    "teniendo en cuenta la tendencia de las ventas."
)

with st.sidebar:
    st.header("Datos y configuración")
    alpha = st.slider(
        "Parámetro alfa (α)",
        min_value=0.01,
        max_value=1.0,
        value=0.30,
        step=0.01,
        help=(
            "Un alfa alto da más importancia a los datos recientes; "
            "uno bajo suaviza más los cambios."
        ),
        format="%.2f",
    )
    st.caption("0,01 suaviza más los cambios; 1,00 responde más a los datos recientes.")

    st.download_button(
        "Descargar plantilla CSV",
        data=CSV_TEMPLATE.encode("utf-8-sig"),
        file_name="plantilla_ventas_ladrillos.csv",
        mime="text/csv",
        width="stretch",
    )
    st.caption(
        "Usa las columnas Año y Ventas (ladrillos), con cantidades sin "
        "separadores de miles."
    )

    csv_widget_revision = st.session_state.data_revision
    uploaded_file = st.file_uploader(
        "Cargar ventas reales desde CSV",
        type=["csv"],
        help="El archivo debe incluir columnas para el año y la cantidad de ladrillos.",
        key=f"csv_upload_{csv_widget_revision}",
    )
    confirm_csv_replace = st.checkbox(
        "Confirmo que deseo sustituir todo el historial guardado por el CSV",
        key=f"confirm_csv_replace_{csv_widget_revision}",
    )
    if uploaded_file is None:
        st.caption("⚪ Archivo CSV: aún no recibido por la aplicación.")
    else:
        st.caption(f"✅ Archivo CSV recibido: {uploaded_file.name}")
    st.caption(
        "✅ Confirmación marcada."
        if confirm_csv_replace
        else "⚪ Confirmación pendiente."
    )
    replace_submitted = st.button(
        "Reemplazar historial",
        type="primary",
        disabled=uploaded_file is None or not confirm_csv_replace,
        width="stretch",
        key=f"replace_history_{csv_widget_revision}",
    )

    if replace_submitted:
        if uploaded_file is None:
            st.session_state.csv_feedback = (
                "error",
                "Selecciona un archivo CSV antes de reemplazar el historial.",
            )
        else:
            try:
                uploaded_data = read_sales_csv(uploaded_file.getvalue())
                normalized_data, import_errors = normalize_sales_data(uploaded_data)
                if import_errors:
                    st.session_state.csv_feedback = ("error", " ".join(import_errors))
                elif normalized_data.empty:
                    st.session_state.csv_feedback = (
                        "error",
                        "El archivo no contiene registros de ventas.",
                    )
                else:
                    try:
                        save_sales_records(normalized_data)
                    except Exception as error:
                        st.session_state.csv_feedback = (
                            "error",
                            "No se pudo guardar el CSV en PostgreSQL: " + str(error),
                        )
                    else:
                        st.session_state.sales_data = normalized_data.copy()
                        st.session_state.persisted_data = normalized_data.copy()
                        st.session_state.data_revision += 1
                        st.session_state.is_sample_data = False
                        st.session_state.csv_feedback = (
                            "success",
                            f"Se guardaron {len(normalized_data)} registros desde el CSV.",
                        )
                        st.rerun()
            except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as error:
                st.session_state.csv_feedback = (
                    "error",
                    f"No se pudo leer el archivo CSV: {error}",
                )

    if st.session_state.csv_feedback:
        feedback_type, feedback_message = st.session_state.csv_feedback
        if feedback_type == "success":
            st.success(feedback_message)
        else:
            st.error(feedback_message)

    with st.form("restore_example_form"):
        st.caption("Restaurar reemplaza el historial guardado.")
        confirm_restore = st.checkbox("Confirmo reemplazar las ventas guardadas")
        restore_submitted = st.form_submit_button(
            "Restaurar datos de ejemplo",
            disabled=not confirm_restore,
            width="stretch",
        )
    if restore_submitted:
        try:
            save_sales_records(SAMPLE_DATA, is_example=True)
        except Exception:
            st.session_state.csv_feedback = (
                "error",
                "No se pudieron restaurar los datos de ejemplo.",
            )
        else:
            st.session_state.sales_data = SAMPLE_DATA.copy()
            st.session_state.persisted_data = SAMPLE_DATA.copy()
            st.session_state.data_revision += 1
            st.session_state.is_sample_data = True
            st.session_state.csv_feedback = (
                "success",
                "Se restauraron y guardaron los datos de ejemplo.",
            )
            st.rerun()

if st.session_state.is_sample_data:
    if st.session_state.persisted_data.empty:
        st.info(
            "Estás viendo datos de ejemplo; aún no hay ventas guardadas. "
            "Guarda los cambios para conservarlos entre reinicios."
        )
    else:
        st.info(
            "El historial guardado contiene datos de ejemplo. Puedes editarlos, "
            "reemplazarlos desde CSV o restaurarlos después."
        )

st.subheader("Ventas históricas")
st.caption(
    "Edita las celdas directamente. Puedes agregar el año actual con las ventas "
    "acumuladas que llevas hasta el momento. Cada año debe tener una sola fila."
)

edited_data = st.data_editor(
    st.session_state.sales_data,
    key=f"sales_editor_{st.session_state.data_revision}",
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_config={
        YEAR_COLUMN: st.column_config.NumberColumn(
            "Año",
            min_value=1,
            max_value=9999,
            step=1,
            format="%d",
            help="Un registro por año, sin saltos entre años.",
        ),
        SALES_COLUMN: st.column_config.NumberColumn(
            "Ventas (ladrillos)",
            min_value=0,
            step=1000,
            format="%d",
            help=(
                "Cantidad de ladrillos vendidos en ese año. "
                "Si el año está en curso, puedes ingresar el acumulado hasta hoy."
            ),
        ),
    },
)

if not edited_data.equals(st.session_state.sales_data):
    st.session_state.sales_data = edited_data.copy()
    st.session_state.csv_feedback = None

changes_pending = not sales_records_equal(
    st.session_state.sales_data,
    st.session_state.persisted_data,
)
edited_normalized, edited_errors = normalize_sales_data(st.session_state.sales_data)

persisted_years = set(
    pd.to_numeric(
        st.session_state.persisted_data.get(
            YEAR_COLUMN, pd.Series(dtype=float)
        ),
        errors="coerce",
    ).dropna().astype(int).tolist()
)
edited_years = (
    set(edited_normalized[YEAR_COLUMN].astype(int).tolist())
    if not edited_errors else set()
)
removed_years = (
    sorted(persisted_years - edited_years) if not edited_errors else []
)

confirm_deletions = False
if removed_years and changes_pending:
    st.warning(
        "Al guardar también se eliminarán del historial los años: "
        + ", ".join(map(str, removed_years))
        + "."
    )
    confirm_deletions = st.checkbox(
        "Confirmo la eliminación de esos años del historial guardado",
        key=(
            "confirm_sales_deletions_"
            f"{st.session_state.data_revision}_{tuple(removed_years)}_"
            f"{hash(tuple(edited_normalized.itertuples(index=False, name=None)))}"
        ),
    )

save_column, status_column = st.columns([1, 3])
with save_column:
    save_clicked = st.button(
        "Guardar cambios",
        type="primary",
        disabled=not changes_pending or (
            bool(removed_years) and not confirm_deletions
        ),
        width="stretch",
    )
with status_column:
    if changes_pending:
        st.warning(
            "Hay cambios sin guardar. Guárdalos para conservarlos al reiniciar la app."
        )
    else:
        st.caption("El historial está guardado en la base de datos.")

if save_clicked:
    records_to_save, save_errors = normalize_sales_data(st.session_state.sales_data)
    if save_errors:
        for save_error in save_errors:
            st.error(save_error)
    elif records_to_save.empty:
        st.error("Conserva al menos un registro antes de guardar.")
    else:
        try:
            save_sales_records(records_to_save)
        except Exception as error:
            st.error("No se pudieron guardar los cambios en PostgreSQL: " + str(error))
        else:
            st.session_state.sales_data = records_to_save.copy()
            st.session_state.persisted_data = records_to_save.copy()
            st.session_state.data_revision += 1
            st.session_state.is_sample_data = False
            st.session_state.csv_feedback = (
                "success",
                "Los cambios quedaron guardados de forma permanente.",
            )
            st.rerun()

source_records, source_errors = normalize_sales_data(st.session_state.sales_data)

if source_errors:
    st.warning("Revisa los datos para calcular el pronóstico:")
    for source_error in source_errors:
        st.error(source_error)
    st.info(
        "Cuando los registros tengan años únicos y cantidades válidas, "
        "aparecerán el pronóstico y los resultados."
    )
    st.stop()

# Se utilizan todos los años ingresados, incluido el año calendario actual.
history, validation_errors = validate_history(source_records)

if validation_errors:
    st.warning("Revisa los datos para calcular el pronóstico:")
    for validation_error in validation_errors:
        st.error(validation_error)
    st.info(
        "Para calcular el pronóstico se necesitan al menos dos años consecutivos, "
        "sin duplicados y con cantidades válidas."
    )
    st.stop()

last_historical_year = int(history[YEAR_COLUMN].iloc[-1])

if last_historical_year >= 9999:
    st.error("No es posible pronosticar después del año 9999.")
    st.stop()

initial_target_year = last_historical_year + 1
target_year = int(
    st.number_input(
        "Año objetivo del pronóstico",
        min_value=last_historical_year + 1,
        max_value=9999,
        value=initial_target_year,
        step=1,
        help=(
            "Por defecto se calcula el año siguiente al último año ingresado. "
            "También puedes elegir un año posterior."
        ),
    )
)

try:
    forecast = forecast_simple_exponential_smoothing(
        history,
        alpha,
        target_year=target_year,
    )
except (ValueError, RuntimeError) as error:
    st.error(f"No fue posible calcular el pronóstico: {error}")
    st.stop()

st.divider()
st.subheader(f"Pronóstico para {forecast.forecast_year}")

metric_columns = st.columns(4)
metric_columns[0].metric(
    f"Pronóstico de ladrillos · {forecast.forecast_year}",
    format_bricks(forecast.forecast_units),
)
metric_columns[1].metric(
    "Último año ingresado",
    str(last_historical_year),
)
metric_columns[2].metric(
    "Ventas del último año ingresado",
    format_bricks(history[SALES_COLUMN].iloc[-1]),
)
metric_columns[3].metric("Alfa (α)", f"{forecast.alpha:.2f}")

historical_years_label = ", ".join(str(year) for year in history[YEAR_COLUMN])
st.caption(
    f"Años utilizados en el cálculo: {historical_years_label}. "
    f"El pronóstico se calcula desde el último año ingresado."
)

last_year_value = float(history[SALES_COLUMN].iloc[-1])
st.info(
    "El modelo utiliza también el último año que ingresaste, aunque sus ventas "
    "sean parciales. Si el año todavía no ha terminado, el resultado debe "
    "interpretarse como una estimación basada en ese acumulado."
)

st.markdown("#### Ventas históricas y pronóstico")

years = history[YEAR_COLUMN].astype(int).tolist()
sales = history[SALES_COLUMN].astype(float).tolist()

figure = go.Figure()
figure.add_trace(
    go.Scatter(
        x=years,
        y=sales,
        mode="lines+markers",
        name="Ventas ingresadas",
        line={"color": "#61A9BD", "width": 3},
        marker={"size": 8},
        hovertemplate="Año %{x}<br>Ventas: %{y:,.0f} ladrillos<extra></extra>",
    )
)

forecast_years = list(
    range(last_historical_year + 1, forecast.forecast_year + 1)
)

forecast_values = forecast.results_table[
    "Pronóstico del modelo (ladrillos)"
].iloc[-len(forecast_years):].astype(float).tolist()

figure.add_trace(
    go.Scatter(
        x=[last_historical_year, *forecast_years],
        y=[last_year_value, *forecast_values],
        mode="lines+markers",
        name="Pronóstico con tendencia",
        line={"color": "#E98E2E", "width": 3, "dash": "dot"},
        marker={"size": 8},
        hovertemplate="Año %{x}<br>Pronóstico: %{y:,.0f} ladrillos<extra></extra>",
    )
)

figure.add_vline(
    x=last_historical_year + 0.5,
    line={"color": "#979797", "dash": "dot", "width": 1},
)
figure.update_layout(
    height=430,
    hovermode="x unified",
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    margin={"l": 10, "r": 10, "t": 35, "b": 10},
    separators=",.",
    xaxis={"title": "Año", "dtick": 1},
    yaxis={"title": "Ladrillos", "rangemode": "tozero"},
)
st.plotly_chart(figure, width="stretch", config={"displaylogo": False})

st.caption(
    "El pronóstico utiliza el método de Holt con tendencia amortiguada. "
    "A diferencia del método anterior, puede reflejar una tendencia de subida "
    "o bajada en las ventas."
)

st.markdown("#### Datos y resultados del método")
display_results = forecast.results_table.copy()

for result_column in (
    "Ventas reales (ladrillos)",
    "Pronóstico del modelo (ladrillos)",
):
    display_results[result_column] = display_results[result_column].map(
        lambda value: "—" if pd.isna(value) else format_bricks(value)
    )

st.dataframe(
    display_results,
    hide_index=True,
    width="stretch",
    column_config={
        "Año": st.column_config.NumberColumn("Año", format="%d"),
        "Tipo": st.column_config.TextColumn("Tipo de dato"),
        "Ventas reales (ladrillos)": st.column_config.TextColumn(
            "Ventas reales (ladrillos)"
        ),
        "Pronóstico del modelo (ladrillos)": st.column_config.TextColumn(
            "Pronóstico del modelo (ladrillos)"
        ),
    },
)

st.caption(
    "El método de Holt utiliza el nivel de ventas y su tendencia para calcular "
    "el pronóstico. El parámetro alfa controla cuánto influyen los datos recientes."
)
