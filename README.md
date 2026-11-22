# Pronóstico de demanda de ladrillos

Aplicación Streamlit en español para administrar ventas anuales de ladrillos, importar CSV, consultar estadísticas y generar pronósticos con suavización exponencial simple (SES).

## Inicio rápido

1. Instala dependencias: `pip install -r requirements.txt`.
2. Configura `DATABASE_URL` como variable de entorno o en `.streamlit/secrets.toml`.
3. Ejecuta `streamlit run streamlit_app.py`.

La tabla PostgreSQL `public.brick_sales` se crea automáticamente al primer acceso. Nunca guardes credenciales en el repositorio.

## Funcionalidades

- Edición de ventas históricas anuales y guardado explícito.
- Importación CSV con detección de columnas, validación y confirmación de reemplazo.
- Plantilla CSV descargable.
- Pronóstico SES con alfa ajustable y horizonte configurable.
- Gráfica Plotly y tabla de niveles suavizados y pronósticos a un paso.
- Exclusión del año calendario actual del cálculo cuando aparece en el historial, sin borrar ese registro.
- Persistencia en PostgreSQL y restauración confirmada de datos de ejemplo.

## Método

El primer valor histórico inicializa el nivel. Para los períodos siguientes:

`nivel_t = α × ventas_t + (1 − α) × nivel_(t−1)`

El último nivel es el pronóstico para el siguiente período. SES no modela tendencia ni estacionalidad.

## Despliegue

Consulta [DEPLOYMENT.md](DEPLOYMENT.md) para desplegar gratuitamente en Streamlit Community Cloud con PostgreSQL administrado en Neon.
