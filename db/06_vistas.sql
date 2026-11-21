-- Vistas: el backend lee SIEMPRE a través de ellas (nunca de las tablas directamente).
-- Se crean después de las tablas (01) y los triggers (05).

-- ---- Detalle (consulta de cliente y apertura) ----
CREATE OR REPLACE VIEW vw_clientes_detalle AS
SELECT c.cod_cliente, c.dni::text AS dni, c.nombres, c.apellido_paterno, c.apellido_materno,
       concat_ws(' ', c.nombres, c.apellido_paterno, c.apellido_materno) AS nombre_completo,
       c.fecha_nacimiento, c.correo, c.estado,
       o.nombre_ocupacion, c.cod_provincia,
       ARRAY(SELECT t.numero_telefono::text FROM telefono_clientes t
             WHERE t.cod_cliente = c.cod_cliente ORDER BY t.numero_telefono) AS telefonos,
       c.calle, c.fecha_emision_dni, c.peruano_residente
FROM cliente c
JOIN ocupacion o ON o.cod_ocupacion = c.cod_ocupacion;

CREATE OR REPLACE VIEW vw_cuentas_detalle AS
SELECT a.numero_cuenta, a.cod_interbancario, a.n_contrato, a.tasa_interes, a.saldo, a.estado,
       c.dni::text AS dni, m.cod_internacional::text AS moneda, a.cod_agencia
FROM cuenta_ahorros a
JOIN cliente c ON c.cod_cliente = a.cod_cliente
JOIN moneda m ON m.cod_moneda = a.cod_moneda;

CREATE OR REPLACE VIEW vw_tarjetas_detalle AS
SELECT t.numero_tarjeta, t.codigo_tarjeta::text AS codigo, t.estado, t.fecha_emision,
       t.fecha_vencimiento, t.marca, t.numero_cuenta, c.dni::text AS dni
FROM tarjeta t
JOIN cuenta_ahorros a ON a.numero_cuenta = t.numero_cuenta
JOIN cliente c ON c.cod_cliente = a.cod_cliente;

-- ---- Listados del CRUD (las columnas llevan el nombre que usa la pantalla) ----
CREATE OR REPLACE VIEW vw_lista_clientes AS
SELECT c.dni::text AS dni, c.nombres, c.apellido_paterno, c.apellido_materno, c.fecha_nacimiento AS nacimiento, c.correo,
       o.nombre_ocupacion AS ocupacion, c.cod_provincia AS provincia, c.estado,
       c.calle, c.fecha_emision_dni AS emision_dni
FROM cliente c
JOIN ocupacion o ON o.cod_ocupacion = c.cod_ocupacion
ORDER BY c.cod_cliente;

CREATE OR REPLACE VIEW vw_lista_agencias AS
SELECT g.cod_agencia AS cod, g.nombre_agencia AS nombre, g.calle, g.cod_provincia AS provincia, g.anexo, g.estado
FROM agencia g
ORDER BY g.cod_agencia;

CREATE OR REPLACE VIEW vw_lista_cuentas AS
SELECT a.numero_cuenta AS numero, c.dni::text AS dni, m.cod_internacional::text AS moneda,
       a.tasa_interes AS tasa, a.saldo, a.estado
FROM cuenta_ahorros a
JOIN cliente c ON c.cod_cliente = a.cod_cliente
JOIN moneda m ON m.cod_moneda = a.cod_moneda
ORDER BY a.numero_cuenta;

CREATE OR REPLACE VIEW vw_lista_tarjetas AS
SELECT t.numero_tarjeta AS numero, t.marca, t.numero_cuenta AS cuenta, t.fecha_vencimiento AS vence, t.estado
FROM tarjeta t
ORDER BY t.fecha_emision DESC, t.numero_tarjeta;

-- ---- Inicio ----
CREATE OR REPLACE VIEW vw_totales AS
SELECT (SELECT COUNT(*) FROM cliente) AS clientes,
       (SELECT COUNT(*) FROM cuenta_ahorros) AS cuentas,
       (SELECT COUNT(*) FROM tarjeta WHERE estado = 1) AS tarjetas_activas;
