# Publicar Pronóstico de demanda de ladrillos

## Arquitectura recomendada (sin costo inicial)

- **Aplicación:** Streamlit Community Cloud (publicación gratuita y enlace `*.streamlit.app`).
- **Base de datos:** Neon Postgres Free (PostgreSQL administrado, 1 GB y cómputo que escala a cero cuando está inactivo).
- No se necesita Replit, un servidor propio ni instalar Python en el dispositivo del usuario.

Los planes gratuitos tienen límites y pueden cambiar. Neon Free limita el cómputo mensual; si se alcanza el límite, la base puede dejar de aceptar consultas hasta el siguiente ciclo o hasta cambiar de plan. No habilites facturación automática si deseas mantener el costo en cero.

## Preparación de la base de datos (una sola vez)

1. Crea una cuenta gratuita en <https://neon.tech/> e inicia un proyecto PostgreSQL.
2. En el panel del proyecto, copia la cadena de conexión **pooled** (si está disponible) para la base de datos creada. Debe comenzar por `postgresql://` y usar SSL (`sslmode=require`).
3. No compartas la cadena ni la publiques en GitHub. Contiene la contraseña de la base de datos.
4. No es necesario ejecutar SQL manualmente: `database.py` crea `public.brick_sales` de forma segura la primera vez que la aplicación se conecta. La tabla almacena `year`, `quantity` e `is_example`.

## Publicación en Streamlit Community Cloud

1. Descomprime el ZIP final y sube el contenido de esta carpeta a un repositorio nuevo de GitHub. Puede ser público o privado; Community Cloud requiere autorización al repositorio.
2. Abre <https://share.streamlit.io/> e inicia sesión.
3. Pulsa **Create app** y selecciona el repositorio, la rama `main` y el archivo `streamlit_app.py`.
4. Abre **Advanced settings**. Selecciona Python **3.13** (o una versión compatible disponible).
5. En **Secrets**, pega exactamente lo siguiente, reemplazando el valor por la cadena real de Neon:

   ```toml
   DATABASE_URL = "postgresql://...cadena-real-de-Neon...?sslmode=require"
   ```

6. Pulsa **Deploy**. Cuando termine, Streamlit mostrará una dirección pública `https://....streamlit.app/`. Comparte esa dirección con el usuario final.

La persona que utilice la aplicación no necesita una cuenta de GitHub, Neon, Streamlit ni instalar Python. El propietario sí necesita sus cuentas para administrar la aplicación y la base de datos.

## Ejecución local opcional

Requiere Python 3.11 o superior y acceso a una instancia PostgreSQL:

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copia `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml`, pega la cadena PostgreSQL real y ejecuta:

```bash
streamlit run streamlit_app.py
```

No subas `secrets.toml` al repositorio.

## Persistencia y operación

- Las ediciones de la tabla se guardan al pulsar **Guardar cambios**.
- La importación CSV sustituye el historial únicamente después de validar el archivo y recibir confirmación explícita.
- El historial se conserva en PostgreSQL aunque la aplicación se reinicie o se suspenda.
- La opción de restaurar ejemplos reemplaza los datos guardados y solicita confirmación.
- Si Neon escala a cero, la primera consulta tras un período inactivo puede tardar un poco mientras se reactiva.

## Pruebas ejecutadas antes de entregar

Desde esta carpeta:

```bash
pip install -r requirements.txt
pip install pytest
pytest -q
python -m py_compile database.py forecasting.py streamlit_app.py
```

La suite cubre los cálculos SES, alfa, horizonte de pronóstico, normalización de CSV, años repetidos, años faltantes y detección del año actual incompleto. Una prueba real de lectura/escritura requiere proporcionar una `DATABASE_URL` válida.
