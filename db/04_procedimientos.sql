-- Procedimientos almacenados (funciones y procedimientos PL/pgSQL). El backend solo los invoca (SELECT / CALL).
-- Firmas anteriores (sin calle, emisión del DNI ni confirmación de residencia): se eliminan para no dejar sobrecargas.
DROP FUNCTION IF EXISTS sp_abrir_cuenta(TEXT,TEXT,DATE,TEXT,TEXT,TEXT,INT,TEXT,INT,BOOLEAN);
DROP PROCEDURE IF EXISTS sp_cliente_crear(TEXT,TEXT,DATE,TEXT,TEXT,INT);
DROP PROCEDURE IF EXISTS sp_cliente_editar(TEXT,TEXT,DATE,TEXT,TEXT,INT);
-- Firmas con el nombre en un solo texto (antes de separar nombres, apellido paterno y apellido materno):
DROP FUNCTION IF EXISTS sp_abrir_cuenta(TEXT,TEXT,DATE,TEXT,TEXT,TEXT,INT,TEXT,DATE,BOOLEAN,TEXT,INT,BOOLEAN);
DROP PROCEDURE IF EXISTS sp_cliente_crear(TEXT,TEXT,DATE,TEXT,TEXT,INT,TEXT,DATE,BOOLEAN);
DROP PROCEDURE IF EXISTS sp_cliente_editar(TEXT,TEXT,DATE,TEXT,TEXT,INT,TEXT,DATE);

-- Validación común de los datos propios del cliente (dirección, emisión del DNI, nacionalidad y residencia)
CREATE OR REPLACE FUNCTION fn_validar_datos_cliente(p_calle TEXT, p_emision DATE, p_peruano BOOLEAN) RETURNS VOID AS $$
BEGIN
  IF p_calle IS NULL OR length(btrim(p_calle)) = 0 THEN RAISE EXCEPTION 'La calle (dirección) del cliente es obligatoria'; END IF;
  IF p_emision IS NULL THEN RAISE EXCEPTION 'La fecha de emisión del DNI es obligatoria'; END IF;
  IF p_emision > CURRENT_DATE THEN RAISE EXCEPTION 'La fecha de emisión del DNI no puede ser futura'; END IF;
  IF p_peruano IS NOT TRUE THEN RAISE EXCEPTION 'Es requisito ser de nacionalidad peruana con domicilio y residencia en Perú'; END IF;
END $$ LANGUAGE plpgsql;

-- Los nombres y los dos apellidos son obligatorios y se guardan por separado (primera forma normal)
CREATE OR REPLACE FUNCTION fn_validar_nombre_cliente(p_nombres TEXT, p_ap_pat TEXT, p_ap_mat TEXT) RETURNS VOID AS $$
BEGIN
  IF p_nombres IS NULL OR length(btrim(p_nombres)) = 0 THEN RAISE EXCEPTION 'Los nombres del cliente son obligatorios'; END IF;
  IF p_ap_pat IS NULL OR length(btrim(p_ap_pat)) = 0 THEN RAISE EXCEPTION 'El apellido paterno del cliente es obligatorio'; END IF;
  IF p_ap_mat IS NULL OR length(btrim(p_ap_mat)) = 0 THEN RAISE EXCEPTION 'El apellido materno del cliente es obligatorio'; END IF;
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_emitir_tarjeta(p_cuenta TEXT) RETURNS TEXT AS $$
DECLARE v_num TEXT := (ARRAY['4','5'])[1 + floor(random()*2)::int] || lpad(floor(random()*1e15)::bigint::text, 15, '0');
BEGIN
  INSERT INTO tarjeta VALUES (v_num, lpad(floor(random()*1000)::int::text, 3, '0'), 1, CURRENT_DATE,
    (CURRENT_DATE + INTERVAL '4 years')::date, CASE WHEN v_num LIKE '4%' THEN 'Visa' ELSE 'Mastercard' END, p_cuenta);
  RETURN v_num;
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_reemplazar_tarjeta(p_num TEXT) RETURNS TEXT AS $$
DECLARE v_cta TEXT;
BEGIN  -- tarjeta perdida: queda inactiva y se emite una réplica con otro número
  UPDATE tarjeta SET estado = 0 WHERE numero_tarjeta = p_num RETURNING numero_cuenta INTO v_cta;
  IF v_cta IS NULL THEN RAISE EXCEPTION 'Tarjeta no encontrada'; END IF;
  RETURN sp_emitir_tarjeta(v_cta);
END $$ LANGUAGE plpgsql;

-- p_prov / p_calle / p_emision / p_peruano son datos del CLIENTE (su provincia de residencia, no la de la agencia);
-- p_ag es la agencia elegida. Si el cliente ya existe, sus datos no se modifican.
CREATE OR REPLACE FUNCTION sp_abrir_cuenta(p_dni TEXT, p_nombres TEXT, p_ap_pat TEXT, p_ap_mat TEXT, p_nac DATE, p_correo TEXT, p_tel TEXT,
  p_ocu TEXT, p_prov INT, p_calle TEXT, p_emision DATE, p_peruano BOOLEAN, p_mon TEXT, p_ag INT, p_tarjeta BOOLEAN)
RETURNS TABLE (o_cuenta TEXT, o_tarjeta TEXT) AS $$
DECLARE v_cli INT; v_mon INT; v_cta TEXT; v_tar TEXT;
BEGIN  -- apertura completa en una transacción: cliente, teléfono, cuenta y tarjeta
  SELECT cod_cliente INTO v_cli FROM cliente WHERE dni = p_dni;
  IF v_cli IS NULL THEN
    PERFORM fn_validar_nombre_cliente(p_nombres, p_ap_pat, p_ap_mat);
    PERFORM fn_validar_datos_cliente(p_calle, p_emision, p_peruano);
    INSERT INTO cliente (dni,nombres,apellido_paterno,apellido_materno,fecha_nacimiento,correo,cod_ocupacion,cod_provincia,calle,fecha_emision_dni,peruano_residente)
    VALUES (p_dni,btrim(p_nombres),btrim(p_ap_pat),btrim(p_ap_mat),p_nac,p_correo,(SELECT cod_ocupacion FROM ocupacion WHERE nombre_ocupacion=p_ocu),p_prov,btrim(p_calle),p_emision,p_peruano)
    RETURNING cod_cliente INTO v_cli;
  END IF;
  INSERT INTO telefono_clientes VALUES (v_cli, p_tel) ON CONFLICT DO NOTHING;
  SELECT cod_moneda INTO v_mon FROM moneda WHERE cod_internacional = p_mon;
  IF v_mon IS NULL THEN RAISE EXCEPTION 'Moneda no válida'; END IF;
  v_cta := '001' || lpad(floor(random()*1e17)::bigint::text, 17, '0');
  INSERT INTO cuenta_ahorros (numero_cuenta,cod_interbancario,tasa_interes,cod_cliente,cod_moneda,cod_agencia)
  VALUES (v_cta, '002' || lpad(floor(random()*1e17)::bigint::text, 17, '0'), 3.5, v_cli, v_mon, p_ag);
  IF p_tarjeta THEN v_tar := sp_emitir_tarjeta(v_cta); END IF;
  RETURN QUERY SELECT v_cta, v_tar;
END $$ LANGUAGE plpgsql;

-- =====================================================================
-- Procedimientos del CRUD (CREATE PROCEDURE, se invocan con CALL).
-- La baja de registros es LÓGICA: nunca se ejecuta DELETE, solo estado = 0.
-- Errores "no encontrado" usan el código P0002 (el backend responde 404).
-- =====================================================================

-- ---------- CLIENTE ----------
CREATE OR REPLACE PROCEDURE sp_cliente_crear(p_dni TEXT, p_nombres TEXT, p_ap_pat TEXT, p_ap_mat TEXT, p_nac DATE, p_correo TEXT, p_ocu TEXT, p_prov INT,
  p_calle TEXT, p_emision DATE, p_peruano BOOLEAN DEFAULT TRUE)
LANGUAGE plpgsql AS $$
DECLARE v_ocu INT;
BEGIN
  SELECT cod_ocupacion INTO v_ocu FROM ocupacion WHERE nombre_ocupacion = p_ocu;
  IF v_ocu IS NULL THEN RAISE EXCEPTION 'Ocupación no válida'; END IF;
  PERFORM fn_validar_nombre_cliente(p_nombres, p_ap_pat, p_ap_mat);
  PERFORM fn_validar_datos_cliente(p_calle, p_emision, p_peruano);
  INSERT INTO cliente (dni, nombres, apellido_paterno, apellido_materno, fecha_nacimiento, correo, cod_ocupacion, cod_provincia, calle, fecha_emision_dni, peruano_residente)
  VALUES (p_dni, btrim(p_nombres), btrim(p_ap_pat), btrim(p_ap_mat), p_nac, p_correo, v_ocu, p_prov, btrim(p_calle), p_emision, p_peruano);
END $$;

CREATE OR REPLACE PROCEDURE sp_cliente_editar(p_dni TEXT, p_nombres TEXT, p_ap_pat TEXT, p_ap_mat TEXT, p_nac DATE, p_correo TEXT, p_ocu TEXT, p_prov INT,
  p_calle TEXT, p_emision DATE)
LANGUAGE plpgsql AS $$
DECLARE v_ocu INT;
BEGIN
  SELECT cod_ocupacion INTO v_ocu FROM ocupacion WHERE nombre_ocupacion = p_ocu;
  IF v_ocu IS NULL THEN RAISE EXCEPTION 'Ocupación no válida'; END IF;
  PERFORM fn_validar_nombre_cliente(p_nombres, p_ap_pat, p_ap_mat);
  PERFORM fn_validar_datos_cliente(p_calle, p_emision, TRUE);  -- la nacionalidad/residencia ya quedó confirmada al registrarlo
  UPDATE cliente
     SET nombres = btrim(p_nombres), apellido_paterno = btrim(p_ap_pat), apellido_materno = btrim(p_ap_mat),
         fecha_nacimiento = p_nac, correo = p_correo,
         cod_ocupacion = v_ocu, cod_provincia = p_prov, calle = btrim(p_calle), fecha_emision_dni = p_emision
   WHERE dni = p_dni;
  IF NOT FOUND THEN RAISE EXCEPTION 'Cliente no encontrado' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE OR REPLACE PROCEDURE sp_cliente_eliminar(p_dni TEXT)   -- baja lógica
LANGUAGE plpgsql AS $$
DECLARE v_cod INT;
BEGIN
  SELECT cod_cliente INTO v_cod FROM cliente WHERE dni = p_dni;
  IF v_cod IS NULL THEN RAISE EXCEPTION 'Cliente no encontrado' USING ERRCODE = 'P0002'; END IF;
  IF EXISTS (SELECT 1 FROM cuenta_ahorros WHERE cod_cliente = v_cod AND estado = 1) THEN
    RAISE EXCEPTION 'No se puede dar de baja: el cliente tiene cuentas activas.';
  END IF;
  UPDATE cliente SET estado = 0 WHERE cod_cliente = v_cod;
END $$;

CREATE OR REPLACE PROCEDURE sp_cliente_activar(p_dni TEXT)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE cliente SET estado = 1 WHERE dni = p_dni;
  IF NOT FOUND THEN RAISE EXCEPTION 'Cliente no encontrado' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE OR REPLACE PROCEDURE sp_cliente_agregar_telefono(p_dni TEXT, p_tel TEXT)
LANGUAGE plpgsql AS $$
DECLARE v_cod INT;
BEGIN
  SELECT cod_cliente INTO v_cod FROM cliente WHERE dni = p_dni;
  IF v_cod IS NULL THEN RAISE EXCEPTION 'Cliente no encontrado' USING ERRCODE = 'P0002'; END IF;
  IF EXISTS (SELECT 1 FROM telefono_clientes WHERE cod_cliente = v_cod AND numero_telefono = p_tel) THEN
    RAISE EXCEPTION 'Ese teléfono ya está registrado para el cliente';
  END IF;
  INSERT INTO telefono_clientes (cod_cliente, numero_telefono) VALUES (v_cod, p_tel);
END $$;

-- ---------- AGENCIA ----------
CREATE OR REPLACE PROCEDURE sp_agencia_crear(p_cod INT, p_nombre TEXT, p_calle TEXT, p_prov INT, p_anexo TEXT)
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO agencia (cod_agencia, nombre_agencia, calle, cod_provincia, anexo, estado)
  VALUES (p_cod, p_nombre, p_calle, p_prov, p_anexo, 1);
END $$;

CREATE OR REPLACE PROCEDURE sp_agencia_editar(p_cod INT, p_nombre TEXT, p_calle TEXT, p_prov INT, p_anexo TEXT)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE agencia SET nombre_agencia = p_nombre, calle = p_calle, cod_provincia = p_prov, anexo = p_anexo
   WHERE cod_agencia = p_cod;
  IF NOT FOUND THEN RAISE EXCEPTION 'Agencia no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE OR REPLACE PROCEDURE sp_agencia_eliminar(p_cod INT)   -- baja lógica
LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM agencia WHERE cod_agencia = p_cod) THEN
    RAISE EXCEPTION 'Agencia no encontrada' USING ERRCODE = 'P0002';
  END IF;
  IF EXISTS (SELECT 1 FROM cuenta_ahorros WHERE cod_agencia = p_cod AND estado = 1) THEN
    RAISE EXCEPTION 'No se puede dar de baja: la agencia tiene cuentas activas.';
  END IF;
  UPDATE agencia SET estado = 0 WHERE cod_agencia = p_cod;
END $$;

CREATE OR REPLACE PROCEDURE sp_agencia_activar(p_cod INT)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE agencia SET estado = 1 WHERE cod_agencia = p_cod;
  IF NOT FOUND THEN RAISE EXCEPTION 'Agencia no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;

-- Activa o desactiva una agencia (botón de Administración): desactivar sigue la misma regla que la baja
CREATE OR REPLACE PROCEDURE sp_agencia_cambiar_estado(p_cod INT)
LANGUAGE plpgsql AS $$
DECLARE v_est SMALLINT;
BEGIN
  SELECT estado INTO v_est FROM agencia WHERE cod_agencia = p_cod;
  IF v_est IS NULL THEN RAISE EXCEPTION 'Agencia no encontrada' USING ERRCODE = 'P0002'; END IF;
  IF v_est = 1 THEN CALL sp_agencia_eliminar(p_cod); ELSE CALL sp_agencia_activar(p_cod); END IF;
END $$;

-- ---------- CUENTA DE AHORROS (se crean con sp_abrir_cuenta) ----------
CREATE OR REPLACE PROCEDURE sp_cuenta_editar_tasa(p_num TEXT, p_tasa NUMERIC)
LANGUAGE plpgsql AS $$
BEGIN
  IF p_tasa IS NULL OR p_tasa < 0 OR p_tasa > 100 THEN
    RAISE EXCEPTION 'La tasa de interés debe estar entre 0 y 100';
  END IF;
  UPDATE cuenta_ahorros SET tasa_interes = p_tasa WHERE numero_cuenta = p_num;
  IF NOT FOUND THEN RAISE EXCEPTION 'Cuenta no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE OR REPLACE PROCEDURE sp_cuenta_eliminar(p_num TEXT)   -- baja lógica (el trigger inactiva sus tarjetas)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE cuenta_ahorros SET estado = 0 WHERE numero_cuenta = p_num;
  IF NOT FOUND THEN RAISE EXCEPTION 'Cuenta no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE OR REPLACE PROCEDURE sp_cuenta_activar(p_num TEXT)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE cuenta_ahorros SET estado = 1 WHERE numero_cuenta = p_num;
  IF NOT FOUND THEN RAISE EXCEPTION 'Cuenta no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE OR REPLACE PROCEDURE sp_cuenta_cambiar_estado(p_num TEXT)   -- activa o desactiva (el trigger inactiva sus tarjetas)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE cuenta_ahorros SET estado = 1 - estado WHERE numero_cuenta = p_num;
  IF NOT FOUND THEN RAISE EXCEPTION 'Cuenta no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;

-- ---------- TARJETA (se emiten con sp_emitir_tarjeta / sp_reemplazar_tarjeta) ----------
CREATE OR REPLACE PROCEDURE sp_tarjeta_editar_marca(p_num TEXT, p_marca TEXT)
LANGUAGE plpgsql AS $$
BEGIN
  IF p_marca IS NULL OR btrim(p_marca) = '' THEN RAISE EXCEPTION 'La marca es obligatoria'; END IF;
  UPDATE tarjeta SET marca = btrim(p_marca) WHERE numero_tarjeta = p_num;
  IF NOT FOUND THEN RAISE EXCEPTION 'Tarjeta no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE OR REPLACE PROCEDURE sp_tarjeta_eliminar(p_num TEXT)   -- baja lógica
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE tarjeta SET estado = 0 WHERE numero_tarjeta = p_num;
  IF NOT FOUND THEN RAISE EXCEPTION 'Tarjeta no encontrada' USING ERRCODE = 'P0002'; END IF;
END $$;
