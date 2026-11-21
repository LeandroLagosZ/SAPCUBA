CREATE INDEX idx_provincia_departamento ON provincia (cod_departamento);
CREATE INDEX idx_agencia_provincia ON agencia (cod_provincia);
CREATE INDEX idx_cliente_ocupacion ON cliente (cod_ocupacion);
CREATE INDEX idx_cliente_provincia ON cliente (cod_provincia);
CREATE INDEX idx_cuenta_cliente ON cuenta_ahorros (cod_cliente);
CREATE INDEX idx_cuenta_moneda ON cuenta_ahorros (cod_moneda);
CREATE INDEX idx_cuenta_agencia ON cuenta_ahorros (cod_agencia);
CREATE INDEX idx_tarjeta_cuenta ON tarjeta (numero_cuenta);
