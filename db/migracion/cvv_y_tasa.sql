-- Migración de una base creada antes de estos cambios: el CVV pasa de SMALLINT a CHAR(3) (conserva los ceros
-- iniciales) y la tasa de interés queda limitada a 0-100 también en la tabla. No borra datos.
-- La aplicación (motor_bd.py) la ejecuta sola y luego vuelve a cargar 04, 06, 07 y 08.
DROP VIEW IF EXISTS vw_tarjetas_detalle;   -- depende de codigo_tarjeta; 06_vistas.sql la vuelve a crear
ALTER TABLE tarjeta DROP CONSTRAINT IF EXISTS tarjeta_codigo_tarjeta_check;
ALTER TABLE tarjeta ALTER COLUMN codigo_tarjeta TYPE CHAR(3) USING lpad(codigo_tarjeta::text, 3, '0');
ALTER TABLE tarjeta ADD CONSTRAINT tarjeta_codigo_tarjeta_check CHECK (codigo_tarjeta ~ '^[0-9]{3}$');
ALTER TABLE cuenta_ahorros DROP CONSTRAINT IF EXISTS cuenta_ahorros_tasa_rango;
ALTER TABLE cuenta_ahorros ADD CONSTRAINT cuenta_ahorros_tasa_rango CHECK (tasa_interes BETWEEN 0 AND 100);
