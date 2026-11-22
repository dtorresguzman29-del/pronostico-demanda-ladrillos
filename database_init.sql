-- Opcional: la aplicación ejecuta este CREATE TABLE automáticamente.
CREATE TABLE IF NOT EXISTS public.brick_sales (
    year INTEGER PRIMARY KEY,
    quantity DOUBLE PRECISION NOT NULL CHECK (quantity >= 0),
    is_example BOOLEAN NOT NULL DEFAULT FALSE
);
