# Correcciones realizadas

- Corregido el manejo de excepciones al cargar la base de datos en `streamlit_app.py`.
  Antes, el bloque `except` intentaba mostrar `error` sin haber capturado la excepción
  con `as error`, lo que podía provocar un `NameError` y convertir un problema de
  conexión/configuración de PostgreSQL en un error interno de la aplicación.
- Se conservaron el diseño, las funcionalidades, el modelo SES y el esquema de datos.
- Se conservaron las instrucciones de despliegue en `DEPLOYMENT.md`.

## Verificación

- `python -m py_compile database.py forecasting.py streamlit_app.py`: correcto.
- `pytest -q`: 13 pruebas aprobadas.

## Pendiente para publicar

La aplicación necesita una variable `DATABASE_URL` válida que apunte a una base
PostgreSQL accesible desde el hosting. El ZIP no incluye credenciales ni puede
incluir las bases de datos alojadas en la cuenta de Replit.
