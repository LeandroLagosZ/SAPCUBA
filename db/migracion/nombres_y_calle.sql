-- Migración: (1) separar nombres_completos en nombres, apellido_paterno y apellido_materno (atributos atómicos, como en la
-- Cuarta Entrega) y (2) ampliar la calle de cliente y agencia a 100 caracteres.
-- Reparto de los clientes que ya existían: las dos últimas palabras pasan a ser el apellido paterno y el materno y el
-- resto son los nombres. Si falta alguna parte se guarda 'Sin registrar'. Los apellidos compuestos (por ejemplo
-- «De la Torre») pueden quedar mal repartidos: conviene revisarlos desde Clientes.

-- Las vistas dependen de estas columnas: se eliminan y 06_vistas.sql las vuelve a crear.
DROP VIEW IF EXISTS vw_clientes_detalle, vw_lista_clientes, vw_lista_agencias;

ALTER TABLE cliente ADD COLUMN IF NOT EXISTS nombres VARCHAR(50);
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS apellido_paterno VARCHAR(50);
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS apellido_materno VARCHAR(50);

UPDATE cliente c
   SET nombres          = left(COALESCE(CASE WHEN n.k >= 3 THEN array_to_string(n.p[1:n.k - 2], ' ') ELSE n.p[1] END, 'Sin registrar'), 50),
       apellido_paterno = left(COALESCE(CASE WHEN n.k >= 3 THEN n.p[n.k - 1] WHEN n.k = 2 THEN n.p[2] END, 'Sin registrar'), 50),
       apellido_materno = left(COALESCE(CASE WHEN n.k >= 3 THEN n.p[n.k] END, 'Sin registrar'), 50)
  FROM (SELECT cod_cliente, p, COALESCE(array_length(p, 1), 0) AS k
          FROM (SELECT cod_cliente,
                       string_to_array(btrim(regexp_replace(nombres_completos, '\s+', ' ', 'g')), ' ') AS p
                  FROM cliente) q) n
 WHERE n.cod_cliente = c.cod_cliente AND c.nombres IS NULL;

ALTER TABLE cliente ALTER COLUMN nombres SET NOT NULL;
ALTER TABLE cliente ALTER COLUMN apellido_paterno SET NOT NULL;
ALTER TABLE cliente ALTER COLUMN apellido_materno SET NOT NULL;
ALTER TABLE cliente ADD CONSTRAINT cliente_nombres_check CHECK (length(btrim(nombres)) > 0);
ALTER TABLE cliente ADD CONSTRAINT cliente_apellido_paterno_check CHECK (length(btrim(apellido_paterno)) > 0);
ALTER TABLE cliente ADD CONSTRAINT cliente_apellido_materno_check CHECK (length(btrim(apellido_materno)) > 0);
ALTER TABLE cliente DROP COLUMN nombres_completos;

ALTER TABLE cliente ALTER COLUMN calle TYPE VARCHAR(100);
ALTER TABLE agencia ALTER COLUMN calle TYPE VARCHAR(100);
