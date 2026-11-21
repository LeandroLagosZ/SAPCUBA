-- Reportes (11) y funciones de consulta. Cada reporte es una función almacenada; el backend solo hace
--   SELECT * FROM sp_reporte_xxx();
-- Los reportes marcados [JOIN] reúnen varias tablas con JOIN explícito (10 de 11); solo uno es de una sola tabla.
-- Todas las columnas se convierten (::text, ::bigint, ::int) para que coincidan con RETURNS TABLE.

-- 1 [JOIN] Cuentas por cliente
CREATE OR REPLACE FUNCTION sp_reporte_cuentas_por_cliente()
RETURNS TABLE (cliente TEXT, dni TEXT, numero_cuenta TEXT, moneda TEXT, saldo TEXT) AS $$
  SELECT concat_ws(' ', c.nombres, c.apellido_paterno, c.apellido_materno)::text, c.dni::text, a.numero_cuenta::text, m.cod_internacional::text,
         (m.simbolo || ' ' || to_char(a.saldo, 'FM999999999990.00'))::text
  FROM cuenta_ahorros a
  JOIN cliente c ON c.cod_cliente = a.cod_cliente
  JOIN moneda m ON m.cod_moneda = a.cod_moneda
  ORDER BY c.apellido_paterno, c.apellido_materno, c.nombres, a.numero_cuenta;
$$ LANGUAGE sql STABLE;

-- 2 [JOIN] Cuentas y saldo total por moneda
CREATE OR REPLACE FUNCTION sp_reporte_cuentas_por_moneda()
RETURNS TABLE (moneda TEXT, cuentas BIGINT, saldo_total TEXT) AS $$
  SELECT m.nombre_moneda::text, COUNT(a.numero_cuenta)::bigint,
         (m.simbolo || ' ' || to_char(COALESCE(SUM(a.saldo), 0), 'FM999999999990.00'))::text
  FROM moneda m
  LEFT JOIN cuenta_ahorros a ON a.cod_moneda = m.cod_moneda
  GROUP BY m.cod_moneda, m.nombre_moneda, m.simbolo
  ORDER BY m.cod_moneda;
$$ LANGUAGE sql STABLE;

-- 3 [JOIN] Cuentas por agencia y departamento
CREATE OR REPLACE FUNCTION sp_reporte_cuentas_por_agencia()
RETURNS TABLE (departamento TEXT, agencia TEXT, cuentas BIGINT) AS $$
  SELECT d.nombre_departamento::text, g.nombre_agencia::text, COUNT(a.numero_cuenta)::bigint
  FROM agencia g
  JOIN provincia p ON p.cod_provincia = g.cod_provincia
  JOIN departamento d ON d.cod_departamento = p.cod_departamento
  LEFT JOIN cuenta_ahorros a ON a.cod_agencia = g.cod_agencia
  GROUP BY d.nombre_departamento, g.cod_agencia, g.nombre_agencia
  ORDER BY 1, 2;
$$ LANGUAGE sql STABLE;

-- 4 [JOIN] Clientes con más de una cuenta
CREATE OR REPLACE FUNCTION sp_reporte_clientes_varias_cuentas()
RETURNS TABLE (cliente TEXT, dni TEXT, total_cuentas BIGINT) AS $$
  SELECT concat_ws(' ', c.nombres, c.apellido_paterno, c.apellido_materno)::text, c.dni::text, COUNT(a.numero_cuenta)::bigint
  FROM cliente c
  JOIN cuenta_ahorros a ON a.cod_cliente = c.cod_cliente
  GROUP BY c.cod_cliente, c.nombres, c.apellido_paterno, c.apellido_materno, c.dni
  HAVING COUNT(a.numero_cuenta) > 1
  ORDER BY 3 DESC, 1;
$$ LANGUAGE sql STABLE;

-- 5 [JOIN] Tarjetas inactivas con su titular
CREATE OR REPLACE FUNCTION sp_reporte_tarjetas_inactivas()
RETURNS TABLE (tarjeta TEXT, titular TEXT, cuenta TEXT, marca TEXT, emitida TEXT, vence TEXT) AS $$
  SELECT t.numero_tarjeta::text, concat_ws(' ', c.nombres, c.apellido_paterno, c.apellido_materno)::text, t.numero_cuenta::text, t.marca::text,
         t.fecha_emision::text, t.fecha_vencimiento::text
  FROM tarjeta t
  JOIN cuenta_ahorros a ON a.numero_cuenta = t.numero_cuenta
  JOIN cliente c ON c.cod_cliente = a.cod_cliente
  WHERE t.estado = 0
  ORDER BY t.fecha_emision DESC, t.numero_tarjeta;
$$ LANGUAGE sql STABLE;

-- 6 [JOIN] Clientes y cuentas por ocupación
CREATE OR REPLACE FUNCTION sp_reporte_clientes_por_ocupacion()
RETURNS TABLE (ocupacion TEXT, clientes BIGINT, cuentas BIGINT) AS $$
  SELECT o.nombre_ocupacion::text, COUNT(DISTINCT c.cod_cliente)::bigint, COUNT(a.numero_cuenta)::bigint
  FROM ocupacion o
  LEFT JOIN cliente c ON c.cod_ocupacion = o.cod_ocupacion
  LEFT JOIN cuenta_ahorros a ON a.cod_cliente = c.cod_cliente
  GROUP BY o.cod_ocupacion, o.nombre_ocupacion
  ORDER BY o.cod_ocupacion;
$$ LANGUAGE sql STABLE;

-- 7 [JOIN] Clientes por departamento y provincia
CREATE OR REPLACE FUNCTION sp_reporte_clientes_por_departamento()
RETURNS TABLE (departamento TEXT, provincia TEXT, clientes BIGINT) AS $$
  SELECT d.nombre_departamento::text, p.nombre_provincia::text, COUNT(c.cod_cliente)::bigint
  FROM departamento d
  JOIN provincia p ON p.cod_departamento = d.cod_departamento
  LEFT JOIN cliente c ON c.cod_provincia = p.cod_provincia
  GROUP BY d.cod_departamento, d.nombre_departamento, p.cod_provincia, p.nombre_provincia
  ORDER BY 1, 2;
$$ LANGUAGE sql STABLE;

-- 8 Tarjetas por marca y estado (una sola tabla, sin JOIN)
CREATE OR REPLACE FUNCTION sp_reporte_tarjetas_por_marca()
RETURNS TABLE (marca TEXT, activas BIGINT, inactivas BIGINT, total BIGINT) AS $$
  SELECT t.marca::text,
         (COUNT(*) FILTER (WHERE t.estado = 1))::bigint,
         (COUNT(*) FILTER (WHERE t.estado = 0))::bigint,
         COUNT(*)::bigint
  FROM tarjeta t
  GROUP BY t.marca
  ORDER BY t.marca;
$$ LANGUAGE sql STABLE;

-- 9 [JOIN] Tarjetas activas ordenadas por fecha de vencimiento (días que faltan)
CREATE OR REPLACE FUNCTION sp_reporte_tarjetas_por_vencer()
RETURNS TABLE (tarjeta TEXT, titular TEXT, marca TEXT, vence TEXT, dias_restantes INT) AS $$
  SELECT t.numero_tarjeta::text, concat_ws(' ', c.nombres, c.apellido_paterno, c.apellido_materno)::text, t.marca::text, t.fecha_vencimiento::text,
         (t.fecha_vencimiento - CURRENT_DATE)::int
  FROM tarjeta t
  JOIN cuenta_ahorros a ON a.numero_cuenta = t.numero_cuenta
  JOIN cliente c ON c.cod_cliente = a.cod_cliente
  WHERE t.estado = 1
  ORDER BY t.fecha_vencimiento, c.apellido_paterno, c.apellido_materno, c.nombres;
$$ LANGUAGE sql STABLE;

-- 10 [JOIN] Las 5 cuentas con mayor saldo de cada moneda
CREATE OR REPLACE FUNCTION sp_reporte_mayores_saldos()
RETURNS TABLE (moneda TEXT, puesto BIGINT, cliente TEXT, numero_cuenta TEXT, agencia TEXT, saldo TEXT) AS $$
  SELECT x.moneda, x.puesto, x.cliente, x.cuenta, x.agencia, (x.simbolo || ' ' || to_char(x.saldo, 'FM999999999990.00'))::text
  FROM (
    SELECT m.cod_internacional::text AS moneda, m.simbolo::text AS simbolo,
           ROW_NUMBER() OVER (PARTITION BY m.cod_moneda ORDER BY a.saldo DESC, a.numero_cuenta) AS puesto,
           concat_ws(' ', c.nombres, c.apellido_paterno, c.apellido_materno)::text AS cliente, a.numero_cuenta::text AS cuenta,
           g.nombre_agencia::text AS agencia, a.saldo AS saldo
    FROM cuenta_ahorros a
    JOIN cliente c ON c.cod_cliente = a.cod_cliente
    JOIN agencia g ON g.cod_agencia = a.cod_agencia
    JOIN moneda m ON m.cod_moneda = a.cod_moneda
  ) x
  WHERE x.puesto <= 5
  ORDER BY x.moneda, x.puesto;
$$ LANGUAGE sql STABLE;

-- 11 [JOIN] Cuentas activas que no tienen ninguna tarjeta activa
CREATE OR REPLACE FUNCTION sp_reporte_cuentas_sin_tarjeta()
RETURNS TABLE (cliente TEXT, dni TEXT, numero_cuenta TEXT, moneda TEXT) AS $$
  SELECT concat_ws(' ', c.nombres, c.apellido_paterno, c.apellido_materno)::text, c.dni::text, a.numero_cuenta::text, m.cod_internacional::text
  FROM cuenta_ahorros a
  JOIN cliente c ON c.cod_cliente = a.cod_cliente
  JOIN moneda m ON m.cod_moneda = a.cod_moneda
  LEFT JOIN tarjeta t ON t.numero_cuenta = a.numero_cuenta AND t.estado = 1
  WHERE a.estado = 1 AND t.numero_tarjeta IS NULL
  ORDER BY c.apellido_paterno, c.apellido_materno, c.nombres, a.numero_cuenta;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------
-- Funciones de consulta usadas por el inicio de sesión y la prueba de conexión
-- ---------------------------------------------------------------------
-- El inicio de sesión usa las credenciales del propio motor PostgreSQL: la aplicación se conecta con el usuario y
-- la contraseña escritos en la pantalla de acceso. Esta función dice quién es el usuario conectado y qué rol tiene
-- en SAPCUBA (superusuario o miembro de sapcuba_admin = ADMIN; miembro de sapcuba_agente = AGENTE; otro = sin rol).
-- El nombre que se muestra es el comentario del rol (COMMENT ON ROLE); si no tiene, se muestra el nombre del rol.
CREATE OR REPLACE FUNCTION fn_sesion_actual()
RETURNS TABLE (usuario_login TEXT, nombre_completo TEXT, rol_usuario TEXT) AS $$
  SELECT r.rolname::text,
         COALESCE(shobj_description(r.oid, 'pg_authid'), r.rolname::text)::text,
         CASE
           WHEN r.rolsuper OR EXISTS (SELECT 1 FROM pg_roles g
                                      WHERE g.rolname = 'sapcuba_admin' AND pg_has_role(r.oid, g.oid, 'member')) THEN 'ADMIN'
           WHEN EXISTS (SELECT 1 FROM pg_roles g
                        WHERE g.rolname = 'sapcuba_agente' AND pg_has_role(r.oid, g.oid, 'member')) THEN 'AGENTE'
         END::text
  FROM pg_roles r
  WHERE r.rolname = current_user;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_salud()
RETURNS TABLE (version_bd TEXT, tablas BIGINT, vistas BIGINT, triggers BIGINT, procedimientos BIGINT) AS $$
  SELECT split_part(version(), ',', 1)::text,
         (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE')::bigint,
         (SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public')::bigint,
         (SELECT COUNT(*) FROM pg_trigger WHERE NOT tgisinternal)::bigint,
         (SELECT COUNT(*) FROM pg_proc WHERE proname ~ '^sp_')::bigint;
$$ LANGUAGE sql STABLE;
