-- Migración: dirección del cliente, fecha de emisión del DNI y confirmación de nacionalidad/residencia.
-- Los clientes que ya existían no tienen estos datos: reciben 'Sin registrar' como calle, una emisión del DNI
-- estimada (a los 18 años, sin pasar de hoy) y la confirmación en verdadero; conviene corregirlos desde Clientes.
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS calle VARCHAR(80);
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS fecha_emision_dni DATE;
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS peruano_residente BOOLEAN;
UPDATE cliente SET calle = 'Sin registrar' WHERE calle IS NULL OR length(btrim(calle)) = 0;
UPDATE cliente SET fecha_emision_dni = LEAST((fecha_nacimiento + INTERVAL '18 years')::date, CURRENT_DATE)
 WHERE fecha_emision_dni IS NULL;
UPDATE cliente SET peruano_residente = TRUE WHERE peruano_residente IS NULL;
ALTER TABLE cliente ALTER COLUMN calle SET NOT NULL;
ALTER TABLE cliente ALTER COLUMN fecha_emision_dni SET NOT NULL;
ALTER TABLE cliente ALTER COLUMN peruano_residente SET NOT NULL;
ALTER TABLE cliente ADD CONSTRAINT cliente_calle_check CHECK (length(btrim(calle)) > 0);
ALTER TABLE cliente ADD CONSTRAINT cliente_peruano_residente_check CHECK (peruano_residente);
ALTER TABLE cliente ADD CONSTRAINT cliente_emision_dni_check
  CHECK (fecha_emision_dni <= CURRENT_DATE AND fecha_emision_dni >= fecha_nacimiento);
