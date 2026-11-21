-- Migración de una base creada con la versión anterior (tablas "auditoria" y "usuario", login con bcrypt).
-- La aplicación (motor_bd.py) la ejecuta sola al detectar esas tablas, y después vuelve a cargar
-- 04_procedimientos, 05_triggers, 06_vistas, 07_reportes y 08_roles. No borra datos del negocio.
DROP VIEW IF EXISTS vw_auditoria_reciente, vw_lista_usuarios;

DROP TRIGGER IF EXISTS trg_aud_cliente ON cliente;
DROP TRIGGER IF EXISTS trg_aud_cuenta ON cuenta_ahorros;
DROP TRIGGER IF EXISTS trg_aud_tarjeta ON tarjeta;
DROP TRIGGER IF EXISTS trg_validar_cuenta ON cuenta_ahorros;
DROP TRIGGER IF EXISTS trg_cuenta_inactiva ON cuenta_ahorros;
DROP TRIGGER IF EXISTS trg_validar_tarjeta ON tarjeta;
DROP FUNCTION IF EXISTS fn_auditar();
DROP FUNCTION IF EXISTS fn_validar_cuenta();
DROP FUNCTION IF EXISTS fn_cuenta_inactiva();
DROP FUNCTION IF EXISTS fn_validar_tarjeta();

DROP PROCEDURE IF EXISTS sp_usuario_crear(text, text, text, text);
DROP PROCEDURE IF EXISTS sp_usuario_editar(text, text, text);
DROP PROCEDURE IF EXISTS sp_usuario_eliminar(text);
DROP PROCEDURE IF EXISTS sp_usuario_activar(text);
DROP FUNCTION IF EXISTS fn_es_ultimo_admin(text);
DROP FUNCTION IF EXISTS fn_login_usuario(text);

DROP TABLE IF EXISTS auditoria;
DROP TABLE IF EXISTS usuario;
