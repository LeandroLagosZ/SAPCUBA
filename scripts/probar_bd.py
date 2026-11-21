# Prueba de la base de datos: ejecuta TODAS las vistas, reportes y procedimientos almacenados.
# Todo ocurre dentro de una transacción que se deshace al final (ROLLBACK): no deja datos de prueba.
# Uso (después de crear la base con scripts/crear_base.py):   python scripts/probar_bd.py
import os, sys
import psycopg2

env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env")
if os.path.exists(env):
    os.environ.setdefault("DATABASE_URL", open(env, encoding="utf-8").read().split("DATABASE_URL=")[1].split()[0])
con = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/apertura_cuentas"))
c = con.cursor()
resultados = []


def probar(nombre, sql, params=(), espera_error=None, verificar=None, espera_codigo=None):
    """Ejecuta una sentencia dentro de un SAVEPOINT. Si espera_error está definido, el texto debe aparecer en el error;
    si espera_codigo está definido, el error debe tener ese SQLSTATE (por ejemplo 42501 = sin permiso)."""
    if espera_codigo is not None:
        espera_error = espera_codigo
    c.execute("SAVEPOINT p")
    try:
        c.execute(sql, params)
        filas = c.fetchall() if c.description else []
        if espera_error is not None:
            resultados.append((False, nombre, f"debía fallar con «{espera_error}» y no falló"))
        elif verificar and not verificar(filas):
            resultados.append((False, nombre, f"resultado inesperado: {filas[:3]}"))
        else:
            resultados.append((True, nombre, f"{len(filas)} fila(s)" if c.description else "ok"))
        c.execute("RELEASE SAVEPOINT p")
    except psycopg2.Error as e:
        c.execute("ROLLBACK TO SAVEPOINT p")
        msg = (e.diag.message_primary or str(e)).strip()
        if espera_codigo is not None:
            if e.pgcode == espera_codigo:
                resultados.append((True, nombre, f"rechazado como se esperaba: {msg}"))
            else:
                resultados.append((False, nombre, f"falló con {e.pgcode} y se esperaba {espera_codigo}: {msg}"))
        elif espera_error is not None and espera_error.lower() in msg.lower():
            resultados.append((True, nombre, f"rechazado como se esperaba: {msg}"))
        else:
            resultados.append((False, nombre, msg))


def uno(sql, params=()):
    c.execute(sql, params)
    return c.fetchone()[0]


antes = {t: uno(f"SELECT COUNT(*) FROM {t}") for t in ("cliente", "agencia", "cuenta_ahorros", "tarjeta")}

# ---- Vistas
for v in ("vw_clientes_detalle", "vw_cuentas_detalle", "vw_tarjetas_detalle", "vw_lista_clientes", "vw_lista_agencias",
          "vw_lista_cuentas", "vw_lista_tarjetas", "vw_totales"):
    probar("Vista " + v, f"SELECT * FROM {v}")

# ---- Reportes (11)
reportes = ["cuentas_por_cliente", "cuentas_por_moneda", "cuentas_por_agencia", "clientes_varias_cuentas", "tarjetas_inactivas",
            "clientes_por_ocupacion", "clientes_por_departamento", "tarjetas_por_marca", "tarjetas_por_vencer",
            "mayores_saldos", "cuentas_sin_tarjeta"]
for r in reportes:
    probar("Reporte sp_reporte_" + r, f"SELECT * FROM sp_reporte_{r}()")
probar("Funciones de consulta: fn_salud", "SELECT * FROM fn_salud()", verificar=lambda f: f[0][2] >= 8)
probar("Funciones de consulta: fn_sesion_actual", "SELECT * FROM fn_sesion_actual()", verificar=lambda f: len(f) == 1 and f[0][2] == "ADMIN")

# ---- Cliente
probar("sp_cliente_crear", "CALL sp_cliente_crear('12345678','Cliente de','Prueba','Test','1990-01-01','prueba@test.com','Dependiente',1,'Calle Prueba 1','2015-01-01')")
probar("sp_cliente_crear (ocupación inválida)", "CALL sp_cliente_crear('12345679','X','Prueba','Test','1990-01-01','x@test.com','Inexistente',1,'Calle Prueba 1','2015-01-01')", espera_error="Ocupación")
probar("sp_cliente_crear (DNI repetido)", "CALL sp_cliente_crear('12345678','Otro','Prueba','Test','1990-01-01','otro@test.com','Dependiente',1,'Calle Prueba 1','2015-01-01')", espera_error="")
probar("sp_cliente_editar", "CALL sp_cliente_editar('12345678','Cliente','Editado','Test','1991-02-02','prueba@test.com','Independiente',1,'Calle Prueba 1','2015-01-01')")
probar("sp_cliente_editar (no existe)", "CALL sp_cliente_editar('00000000','X','Prueba','Test','1990-01-01','z@test.com','Dependiente',1,'Calle Prueba 1','2015-01-01')", espera_error="no encontrado")
probar("sp_cliente_agregar_telefono", "CALL sp_cliente_agregar_telefono('12345678','911111111')")
probar("sp_cliente_agregar_telefono (repetido)", "CALL sp_cliente_agregar_telefono('12345678','911111111')", espera_error="ya está registrado")
probar("sp_cliente_eliminar (baja lógica)", "CALL sp_cliente_eliminar('12345678')")
probar("  el cliente sigue en la tabla con estado 0", "SELECT estado FROM cliente WHERE dni = '12345678'", verificar=lambda f: f == [(0,)])
probar("sp_cliente_activar", "CALL sp_cliente_activar('12345678')")

# ---- Cuenta y tarjeta (con datos de ejemplo: DNI 60967097)
probar("sp_cliente_eliminar (con cuentas activas)", "CALL sp_cliente_eliminar('60967097')", espera_error="cuentas activas")
probar("sp_abrir_cuenta", "SELECT * FROM sp_abrir_cuenta('12345678','Cliente','Editado','Test','1991-02-02','prueba@test.com','922222222','Independiente',1,'Calle Prueba 1','2015-01-01',TRUE,'PEN',1,TRUE)",
       verificar=lambda f: len(f) == 1 and f[0][0] and f[0][1])
# ---- Datos propios del cliente: dirección, emisión del DNI, nacionalidad/residencia y provincia distinta de la agencia
probar("sp_abrir_cuenta (cliente en otra provincia que la agencia)", "SELECT * FROM sp_abrir_cuenta('11111111','Cliente','Provincia','Test','1990-03-03','prov@test.com','955555555','Dependiente',2,'Av. Lima 50','2015-01-01',TRUE,'PEN',1,FALSE)",
       verificar=lambda f: len(f) == 1)
probar("  se guardan la provincia del cliente (no la de la agencia), la calle y la emisión del DNI", "SELECT cod_provincia, calle, fecha_emision_dni::text, peruano_residente FROM cliente WHERE dni = '11111111'",
       verificar=lambda f: f == [(2, 'Av. Lima 50', '2015-01-01', True)])
probar("sp_abrir_cuenta (sin calle)", "SELECT * FROM sp_abrir_cuenta('22222222','Sin','Calle','Test','1990-03-03','sc@test.com','955555556','Dependiente',1,'  ','2015-01-01',TRUE,'PEN',1,FALSE)", espera_error="calle")
probar("sp_abrir_cuenta (sin emisión del DNI)", "SELECT * FROM sp_abrir_cuenta('22222223','Sin','Emision','Test','1990-03-03','se@test.com','955555557','Dependiente',1,'Calle 1',NULL,TRUE,'PEN',1,FALSE)", espera_error="emisión")
probar("sp_abrir_cuenta (no peruano residente)", "SELECT * FROM sp_abrir_cuenta('22222224','Extranjero','Prueba','Test','1990-03-03','ex@test.com','955555558','Dependiente',1,'Calle 1','2015-01-01',FALSE,'PEN',1,FALSE)", espera_error="nacionalidad peruana")
probar("sp_cliente_crear (emisión futura)", "CALL sp_cliente_crear('22222225','Futuro','Prueba','Test','1990-03-03','fu@test.com','Dependiente',1,'Calle 1','2999-01-01')", espera_error="futura")
# ---- Nombre atómico (nombres, apellido paterno y apellido materno) y calle de hasta 100 caracteres
probar("cliente: ya no existe la columna nombres_completos", "SELECT 1 FROM information_schema.columns WHERE table_name = 'cliente' AND column_name = 'nombres_completos'", verificar=lambda f: len(f) == 0)
probar("cliente: nombres, apellido_paterno y apellido_materno son columnas", "SELECT column_name FROM information_schema.columns WHERE table_name = 'cliente' AND column_name IN ('nombres', 'apellido_paterno', 'apellido_materno')", verificar=lambda f: len(f) == 3)
probar("vw_clientes_detalle: nombre_completo se arma con las tres partes", "SELECT nombre_completo FROM vw_clientes_detalle WHERE dni = '60967097'", verificar=lambda f: f and f[0][0] == "Juan José Pérez Gómez")
probar("sp_cliente_crear (sin apellido paterno)", "CALL sp_cliente_crear('22222226','Ana','  ','Test','1990-03-03','a1@test.com','Dependiente',1,'Calle 1','2015-01-01')", espera_error="apellido paterno")
probar("sp_cliente_crear (sin apellido materno)", "CALL sp_cliente_crear('22222226','Ana','Prueba','','1990-03-03','a2@test.com','Dependiente',1,'Calle 1','2015-01-01')", espera_error="apellido materno")
probar("sp_abrir_cuenta (sin nombres)", "SELECT * FROM sp_abrir_cuenta('22222227','','Prueba','Test','1990-03-03','a3@test.com','955555559','Dependiente',1,'Calle 1','2015-01-01',TRUE,'PEN',1,FALSE)", espera_error="nombres")
probar("sp_cliente_editar (sin apellido materno)", "CALL sp_cliente_editar('12345678','Cliente','Editado',NULL,'1991-02-02','prueba@test.com','Independiente',1,'Calle Prueba 1','2015-01-01')", espera_error="apellido materno")
probar("sp_cliente_crear (calle de 100 caracteres)", "CALL sp_cliente_crear('22222228','Ana','Prueba','Test','1990-03-03','a4@test.com','Dependiente',1,repeat('C',100),'2015-01-01')")
probar("sp_cliente_crear (calle de 101 caracteres)", "CALL sp_cliente_crear('22222229','Ana','Prueba','Test','1990-03-03','a5@test.com','Dependiente',1,repeat('C',101),'2015-01-01')", espera_codigo="22001")
probar("sp_agencia_crear (calle de 100 caracteres)", "CALL sp_agencia_crear(90, 'Agencia Prueba Calle', repeat('A',100), 1, '9090')")
cta = uno("SELECT numero_cuenta FROM cuenta_ahorros a JOIN cliente c ON c.cod_cliente = a.cod_cliente WHERE c.dni = '12345678' LIMIT 1")
tar = uno("SELECT numero_tarjeta FROM tarjeta WHERE numero_cuenta = %s LIMIT 1", (cta,))
probar("sp_cuenta_editar_tasa", "CALL sp_cuenta_editar_tasa(%s, 4.25)", (cta,))
probar("sp_cuenta_editar_tasa (fuera de rango)", "CALL sp_cuenta_editar_tasa(%s, 500)", (cta,), espera_error="entre 0 y 100")
probar("sp_tarjeta_editar_marca", "CALL sp_tarjeta_editar_marca(%s, 'Visa Gold')", (tar,))
probar("sp_emitir_tarjeta", "SELECT sp_emitir_tarjeta(%s)", (cta,))
probar("sp_reemplazar_tarjeta", "SELECT sp_reemplazar_tarjeta(%s)", (tar,))
probar("sp_tarjeta_eliminar (baja lógica)", "CALL sp_tarjeta_eliminar(%s)", (tar,))
probar("sp_cuenta_cambiar_estado (desactiva)", "CALL sp_cuenta_cambiar_estado(%s)", (cta,))
probar("  el trigger inactivó las tarjetas de la cuenta", "SELECT COUNT(*) FROM tarjeta WHERE numero_cuenta = %s AND estado = 1", (cta,), verificar=lambda f: f == [(0,)])
probar("sp_cuenta_cambiar_estado (activa)", "CALL sp_cuenta_cambiar_estado(%s)", (cta,))
probar("sp_cuenta_eliminar (baja lógica)", "CALL sp_cuenta_eliminar(%s)", (cta,))
probar("sp_cuenta_activar", "CALL sp_cuenta_activar(%s)", (cta,))
probar("sp_cuenta_eliminar (no existe)", "CALL sp_cuenta_eliminar('0')", espera_error="no encontrada")

# ---- Agencia
probar("sp_agencia_crear", "CALL sp_agencia_crear(99,'Agencia de Prueba','Calle 1',1,'9999')")
probar("sp_agencia_editar", "CALL sp_agencia_editar(99,'Agencia Editada','Calle 2',1,'9999')")
probar("sp_agencia_eliminar (con cuentas activas)", "CALL sp_agencia_eliminar(1)", espera_error="cuentas activas")
probar("sp_agencia_cambiar_estado (desactiva)", "CALL sp_agencia_cambiar_estado(99)")
probar("sp_agencia_cambiar_estado (activa)", "CALL sp_agencia_cambiar_estado(99)")
probar("sp_agencia_eliminar (baja lógica)", "CALL sp_agencia_eliminar(99)")
probar("sp_agencia_activar", "CALL sp_agencia_activar(99)")

# ---- Triggers de reglas de negocio
cta_t = uno("SELECT numero_cuenta FROM cuenta_ahorros WHERE cod_cliente = 1001 AND cod_moneda = 1 LIMIT 1")
probar("trg_cuenta_inmutable (cambiar la moneda)", "UPDATE cuenta_ahorros SET cod_moneda = 2 WHERE numero_cuenta = %s", (cta_t,), espera_error="No se pueden modificar")
probar("trg_cuenta_inmutable (cambiar el titular)", "UPDATE cuenta_ahorros SET cod_cliente = 1002 WHERE numero_cuenta = %s", (cta_t,), espera_error="No se pueden modificar")
probar("trg_validar_cuenta (agencia inactiva)", "SELECT * FROM sp_abrir_cuenta('87654320','Cliente','Agencia','Test','1990-05-05','agencia@test.com','944444444','Dependiente',1,'Calle Prueba 1','2015-01-01',TRUE,'PEN',5,FALSE)", espera_error="agencia no está activa")
c.execute("UPDATE cuenta_ahorros SET estado = 0 WHERE numero_cuenta = %s", (cta_t,))
probar("trg_validar_tarjeta (cuenta inactiva)", "SELECT sp_emitir_tarjeta(%s)", (cta_t,), espera_error="cuenta está inactiva")
probar("trg_tarjeta_reactivar (cuenta inactiva)", "UPDATE tarjeta SET estado = 1 WHERE numero_cuenta = %s", (cta_t,), espera_error="No se puede activar la tarjeta")
c.execute("UPDATE cuenta_ahorros SET estado = 1 WHERE numero_cuenta = %s", (cta_t,))

# ---- Restricciones de la tabla
probar("CVV con ceros iniciales se conserva (007)", "UPDATE tarjeta SET codigo_tarjeta = '007' WHERE numero_tarjeta = '4111111111111111'")
probar("  la vista muestra 007", "SELECT codigo FROM vw_tarjetas_detalle WHERE numero_tarjeta = '4111111111111111'", verificar=lambda f: f == [("007",)])
probar("CVV de 1 o 2 dígitos se rechaza", "UPDATE tarjeta SET codigo_tarjeta = '7' WHERE numero_tarjeta = '4111111111111111'", espera_codigo="23514")
probar("Tasa de interés fuera de 0-100 se rechaza en la tabla", "UPDATE cuenta_ahorros SET tasa_interes = 500 WHERE numero_cuenta = %s", (cta_t,), espera_codigo="23514")

# ---- Roles de PostgreSQL (el inicio de sesión usa el usuario y la contraseña del motor; el permiso lo da GRANT)
# SET ROLE actúa como ese usuario sin conocer su contraseña; requiere que esta prueba corra con un superusuario.
probar("Roles creados (sapcuba_admin, sapcuba_agente, admin, agente)", "SELECT rolname FROM pg_roles WHERE rolname IN ('sapcuba_admin','sapcuba_agente','admin','agente')",
       verificar=lambda f: len(f) == 4)
c.execute('SET LOCAL ROLE "agente"')
probar("agente: fn_sesion_actual = AGENTE", "SELECT * FROM fn_sesion_actual()", verificar=lambda f: len(f) == 1 and f[0][0] == "agente" and f[0][2] == "AGENTE")
probar("agente: lee vistas y reportes", "SELECT (SELECT COUNT(*) FROM vw_totales), (SELECT COUNT(*) FROM sp_reporte_cuentas_por_moneda())")
probar("agente: sp_abrir_cuenta", "SELECT * FROM sp_abrir_cuenta('87654321','Agente','Prueba','Test','1990-05-05','agente@test.com','933333333','Dependiente',1,'Calle Prueba 1','2015-01-01',TRUE,'PEN',1,TRUE)",
       verificar=lambda f: len(f) == 1 and f[0][0])
probar("agente: sp_cliente_editar", "CALL sp_cliente_editar('87654321','Agente','Editado','Test','1990-05-05','agente@test.com','Independiente',1,'Calle Prueba 1','2015-01-01')")
probar("agente: sp_cuenta_cambiar_estado", "CALL sp_cuenta_cambiar_estado(%s)", (cta_t,))
probar("agente: sp_cuenta_cambiar_estado (reactiva)", "CALL sp_cuenta_cambiar_estado(%s)", (cta_t,))
probar("agente sin permiso: sp_cliente_eliminar", "CALL sp_cliente_eliminar('87654321')", espera_codigo="42501")
probar("agente sin permiso: sp_cuenta_eliminar", "CALL sp_cuenta_eliminar(%s)", (cta_t,), espera_codigo="42501")
probar("agente sin permiso: sp_agencia_crear", "CALL sp_agencia_crear(98,'Agencia X','Calle 3',1,'9898')", espera_codigo="42501")
probar("agente sin permiso: UPDATE directo en agencia", "UPDATE agencia SET estado = 0 WHERE cod_agencia = 1", espera_codigo="42501")
probar("agente sin permiso: DELETE directo en cliente", "DELETE FROM cliente WHERE dni = '87654321'", espera_codigo="42501")
c.execute("RESET ROLE")
c.execute('SET LOCAL ROLE "admin"')
probar("admin: fn_sesion_actual = ADMIN", "SELECT * FROM fn_sesion_actual()", verificar=lambda f: len(f) == 1 and f[0][2] == "ADMIN")
probar("admin: sp_cliente_crear", "CALL sp_cliente_crear('87654322','Cliente','Admin','Test','1990-01-01','admin@test.com','Dependiente',1,'Calle Prueba 1','2015-01-01')")
probar("admin: sp_cliente_eliminar", "CALL sp_cliente_eliminar('87654322')")
probar("admin: sp_agencia_crear", "CALL sp_agencia_crear(98,'Agencia X','Calle 3',1,'9898')")
probar("admin sin DELETE directo (las bajas son lógicas)", "DELETE FROM cliente WHERE dni = '87654321'", espera_codigo="42501")
c.execute("RESET ROLE")

# ---- Ninguna baja borró filas
despues = {t: uno(f"SELECT COUNT(*) FROM {t}") for t in antes}
fisico = [t for t in antes if despues[t] < antes[t]]
resultados.append((not fisico, "Ninguna baja borró filas (solo estado = 0)", f"tablas con menos filas: {fisico}" if fisico else "ok"))

con.rollback()  # no se guarda nada de lo anterior
con.close()

fallas = [r for r in resultados if not r[0]]
for ok, nombre, detalle in resultados:
    print(("OK    " if ok else "FALLA ") + nombre + "  ->  " + detalle)
print(f"\n{len(resultados) - len(fallas)} de {len(resultados)} pruebas correctas. Se hizo ROLLBACK: la base quedó como estaba.")
sys.exit(1 if fallas else 0)
