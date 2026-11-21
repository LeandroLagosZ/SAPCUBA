-- Reglas de negocio con triggers. No hay tabla de auditoría: el motor rechaza los datos que incumplen estas reglas.

-- Una cuenta nueva exige agencia, moneda y cliente activos
CREATE FUNCTION fn_validar_cuenta() RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM agencia WHERE cod_agencia = NEW.cod_agencia AND estado = 1) THEN
    RAISE EXCEPTION 'La agencia no está activa'; END IF;
  IF NOT EXISTS (SELECT 1 FROM moneda WHERE cod_moneda = NEW.cod_moneda AND estado = 1) THEN
    RAISE EXCEPTION 'La moneda no está disponible'; END IF;
  IF NOT EXISTS (SELECT 1 FROM cliente WHERE cod_cliente = NEW.cod_cliente AND estado = 1) THEN
    RAISE EXCEPTION 'El cliente está inactivo'; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validar_cuenta BEFORE INSERT ON cuenta_ahorros FOR EACH ROW EXECUTE FUNCTION fn_validar_cuenta();

-- Los datos que identifican a la cuenta no se modifican (solo cambian la tasa, el saldo y el estado)
CREATE FUNCTION fn_cuenta_inmutable() RETURNS trigger AS $$
BEGIN
  IF NEW.numero_cuenta      IS DISTINCT FROM OLD.numero_cuenta
  OR NEW.cod_interbancario  IS DISTINCT FROM OLD.cod_interbancario
  OR NEW.n_contrato         IS DISTINCT FROM OLD.n_contrato
  OR NEW.cod_cliente        IS DISTINCT FROM OLD.cod_cliente
  OR NEW.cod_moneda         IS DISTINCT FROM OLD.cod_moneda THEN
    RAISE EXCEPTION 'No se pueden modificar el número, el CCI, el contrato, el titular ni la moneda de una cuenta';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_cuenta_inmutable BEFORE UPDATE ON cuenta_ahorros FOR EACH ROW EXECUTE FUNCTION fn_cuenta_inmutable();

-- No se emiten tarjetas para una cuenta inactiva
CREATE FUNCTION fn_validar_tarjeta() RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM cuenta_ahorros WHERE numero_cuenta = NEW.numero_cuenta AND estado = 1) THEN
    RAISE EXCEPTION 'No se puede emitir tarjeta: la cuenta está inactiva'; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validar_tarjeta BEFORE INSERT ON tarjeta FOR EACH ROW EXECUTE FUNCTION fn_validar_tarjeta();

-- Una tarjeta inactiva no vuelve a activarse si su cuenta está inactiva
CREATE FUNCTION fn_tarjeta_reactivar() RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM cuenta_ahorros WHERE numero_cuenta = NEW.numero_cuenta AND estado = 1) THEN
    RAISE EXCEPTION 'No se puede activar la tarjeta: la cuenta está inactiva'; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_tarjeta_reactivar BEFORE UPDATE OF estado ON tarjeta
  FOR EACH ROW WHEN (OLD.estado = 0 AND NEW.estado = 1) EXECUTE FUNCTION fn_tarjeta_reactivar();

-- Al desactivar una cuenta, sus tarjetas activas pasan a inactivas
CREATE FUNCTION fn_cuenta_inactiva() RETURNS trigger AS $$
BEGIN
  UPDATE tarjeta SET estado = 0 WHERE numero_cuenta = NEW.numero_cuenta AND estado = 1;
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_cuenta_inactiva AFTER UPDATE OF estado ON cuenta_ahorros
  FOR EACH ROW WHEN (OLD.estado = 1 AND NEW.estado = 0) EXECUTE FUNCTION fn_cuenta_inactiva();
