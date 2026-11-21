"""SAPCUBA - servidor HTTP del sistema de apertura de cuentas.

Sin frameworks: solo la librería estándar de Python (http.server) más una librería auxiliar,
psycopg2 (conexión a PostgreSQL).

Inicio de sesión: se usan las credenciales del propio motor PostgreSQL. El usuario y la contraseña de la pantalla de
acceso se prueban conectándose a la base; no existe tabla de usuarios. Cada petición posterior se ejecuta con la
conexión de ESE usuario, de modo que los permisos (GRANT) de db/08_roles.sql los aplica el motor.

Regla de oro del backend: NO contiene sentencias INSERT / UPDATE / DELETE ni consultas de reportes.
  - Escrituras  -> CALL sp_xxx(...)               (procedimientos almacenados, db/04_procedimientos.sql)
  - Reportes    -> SELECT * FROM sp_reporte_xxx() (db/07_reportes.sql)
  - Lecturas    -> SELECT * FROM vw_xxx           (vistas, db/06_vistas.sql)
Las bajas son lógicas (estado = 0) y las hacen los procedimientos.

Desarrollo:  cd backend && python main.py [puerto]     (abre http://localhost:8000)
"""
import json, mimetypes, os, re, secrets, sys, threading, time, traceback
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import psycopg2, psycopg2.extensions, psycopg2.extras

import motor_bd

# Rutas: funcionan igual con "python main.py" y dentro del .exe (PyInstaller)
EMPAQUETADO = getattr(sys, "frozen", False)
CARPETA_APP = os.path.dirname(sys.executable) if EMPAQUETADO else os.path.dirname(os.path.abspath(__file__))
CARPETA_RECURSOS = sys._MEIPASS if EMPAQUETADO else os.path.join(CARPETA_APP, "..")
CARPETA_FRONTEND = os.path.abspath(os.path.join(CARPETA_RECURSOS, "frontend"))

_env = os.path.join(CARPETA_APP, ".env")  # lo crea scripts/crear_base.py (o CrearBase.exe, junto al .exe)
if os.path.exists(_env):
    for _l in open(_env, encoding="utf-8"):
        if "=" in _l and not _l.startswith("#"):
            _k, _v = _l.strip().split("=", 1)
            os.environ.setdefault(_k, _v)

DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/apertura_cuentas")
DURACION_SESION = 8 * 3600  # la sesión vence a las 8 horas
ORIGEN_LOCAL = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")
MAX_CUERPO = 1_000_000


class ApiError(Exception):
    def __init__(self, estado: int, detalle: str):
        super().__init__(detalle)
        self.estado, self.detalle = estado, detalle


# ----------------------------------------------------------------------------- seguridad y base de datos
# Sesiones en memoria: token aleatorio -> usuario y contraseña de PostgreSQL (solo viven en este proceso, nunca se
# guardan en disco ni se envían al navegador; el navegador solo recibe el token).
SESIONES = {}
_BLOQUEO = threading.Lock()
_ctx = threading.local()  # sesión de la petición que se está atendiendo (cada petición corre en su propio hilo)

_AUTENTICACION = ("authentication", "autentific", "autentic", "password", "contraseña", "role ", "rol ", "pg_hba")


def _conectar(usuario: str, clave: str):
    """Abre una conexión a PostgreSQL con las credenciales dadas. Devuelve None si el motor las rechaza."""
    datos = psycopg2.extensions.parse_dsn(DSN)  # servidor, puerto y base vienen del DSN; usuario y clave, de la persona
    datos.update(user=usuario, password=clave, connect_timeout=10)
    try:
        return psycopg2.connect(**datos)
    except psycopg2.OperationalError as e:
        if any(p in str(e).lower() for p in _AUTENTICACION):
            return None
        raise


def iniciar_sesion(usuario: str, clave: str) -> dict:
    con = _conectar(usuario, clave)
    if con is None:
        time.sleep(0.5)  # frena los intentos repetidos de adivinar contraseñas
        raise ApiError(401, "Usuario o contraseña incorrectos")
    try:
        with con, con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("SELECT * FROM fn_sesion_actual()")
            u = c.fetchone()
    finally:
        con.close()
    if not u or not u["rol_usuario"]:
        raise ApiError(403, "Este usuario de PostgreSQL no tiene acceso a SAPCUBA (debe pertenecer a sapcuba_admin o sapcuba_agente)")
    ahora = time.time()
    token = secrets.token_urlsafe(32)
    with _BLOQUEO:
        for k in [k for k, s in SESIONES.items() if s["x"] <= ahora]:  # limpia las sesiones vencidas
            del SESIONES[k]
        SESIONES[token] = {"u": u["usuario_login"], "k": clave, "n": u["nombre_completo"], "r": u["rol_usuario"],
                           "x": ahora + DURACION_SESION}
    return {"token": token, "usuario": u["usuario_login"], "nombre": u["nombre_completo"], "rol": u["rol_usuario"]}


PUBLICAS = ("/api/login", "/api/ping", "/api/latido", "/api/cerrar")


def verificar(ruta: str, metodo: str, autorizacion: str):
    """Se ejecuta en TODAS las rutas /api excepto las públicas. Valida la sesión y el rol; devuelve la sesión."""
    if ruta in PUBLICAS:
        return None
    token = autorizacion.removeprefix("Bearer ").strip()
    with _BLOQUEO:
        s = SESIONES.get(token)
        if s and s["x"] <= time.time():
            del SESIONES[token]
            s = None
    if not s:
        raise ApiError(401, "Sesión no válida o expirada")
    solo_admin = (metodo == "DELETE" or ruta.endswith("/activar") or ruta.startswith("/api/respaldos")
                  or (metodo != "GET" and ruta.startswith(("/api/agencias", "/api/crud/agencias"))))
    if s["r"] != "ADMIN" and solo_admin:  # además, el motor rechaza lo que el rol no puede (GRANT de db/08_roles.sql)
        raise ApiError(403, "No tienes permiso para esta acción")
    s["token"] = token
    return s


@contextmanager
def cur():
    """Conexión con el usuario de la sesión actual: una sola transacción (commit al salir, rollback si hay error)."""
    s = getattr(_ctx, "sesion", None)
    if not s:
        raise ApiError(401, "Sesión no válida o expirada")
    con = _conectar(s["u"], s["k"])
    if con is None:  # la contraseña o el rol cambiaron en PostgreSQL: se cierra la sesión
        with _BLOQUEO:
            SESIONES.pop(s["token"], None)
        raise ApiError(401, "Sesión no válida o expirada")
    try:
        with con:
            with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
                yield c
    finally:
        con.close()


def llamar(c, procedimiento: str, *args) -> None:
    """CALL de un procedimiento almacenado. El nombre sale de las tablas internas de este archivo, nunca del cliente."""
    c.execute("CALL " + procedimiento + "(" + ", ".join(["%s"] * len(args)) + ")", args)


def renombrar(fila: dict, mapa: dict) -> dict:
    return {nuevo: fila[viejo] for viejo, nuevo in mapa.items()}


# Nombres de columna de las vistas -> nombres que usa la pantalla
MAPA_CUENTA = {"numero_cuenta": "num", "cod_interbancario": "cci", "n_contrato": "con", "tasa_interes": "tasa",
               "saldo": "sal", "estado": "e", "dni": "dni", "moneda": "mon", "cod_agencia": "ag"}
MAPA_TARJETA = {"numero_tarjeta": "num", "codigo": "cvv", "estado": "e", "fecha_emision": "em", "fecha_vencimiento": "ve",
                "marca": "mar", "numero_cuenta": "cta"}
MAPA_CLIENTE = {"cod_cliente": "cod", "dni": "dni", "nombre_completo": "nom", "nombres": "nombres", "apellido_paterno": "ap",
                "apellido_materno": "am", "fecha_nacimiento": "nac", "correo": "mail",
                "estado": "e", "nombre_ocupacion": "ocu", "cod_provincia": "prov", "telefonos": "tel",
                "calle": "calle", "fecha_emision_dni": "emi", "peruano_residente": "per"}


def _serializar(o):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)


def _requerir(d: dict, campos) -> None:
    faltan = [k for k in campos if d.get(k) in (None, "")]
    if faltan:
        raise ApiError(400, "Faltan datos: " + ", ".join(faltan))


# ----------------------------------------------------------------------------- rutas
class Peticion:
    def __init__(self, metodo, ruta, cabeceras, cuerpo):
        self.metodo, self.ruta, self.cabeceras, self.cuerpo = metodo, ruta, cabeceras, cuerpo


RUTAS = []


def ruta(metodo: str, patron: str):
    def registrar(f):
        RUTAS.append((metodo, re.compile("^" + patron + "$"), f))
        return f
    return registrar


@ruta("POST", r"/api/login")
def login(p):  # usuario y contraseña de PostgreSQL
    _requerir(p.cuerpo, ("usuario", "clave"))
    return iniciar_sesion(str(p.cuerpo["usuario"]).strip(), str(p.cuerpo["clave"]))


@ruta("POST", r"/api/logout")
def logout(p):  # olvida la sesión (y con ella la contraseña que estaba en memoria)
    with _BLOQUEO:
        SESIONES.pop(_ctx.sesion["token"], None)
    return {"ok": True}


@ruta("GET", r"/api/catalogos")
def catalogos(p):
    with cur() as c:
        c.execute("SELECT * FROM vw_lista_agencias")
        ag = [{"c": a["cod"], "n": a["nombre"], "p": a["provincia"], "e": a["estado"]} for a in c.fetchall()]
        c.execute("SELECT * FROM vw_totales")
        t = c.fetchone()
        c.execute("SELECT cod_departamento, nombre_departamento FROM departamento ORDER BY nombre_departamento")
        deps = {r["cod_departamento"]: r["nombre_departamento"] for r in c.fetchall()}
        c.execute("SELECT cod_provincia, cod_departamento, nombre_provincia FROM provincia ORDER BY nombre_provincia")
        provs = [[r["cod_provincia"], r["cod_departamento"], r["nombre_provincia"]] for r in c.fetchall()]
        c.execute("SELECT cod_internacional, nombre_moneda, simbolo FROM moneda WHERE estado = 1 ORDER BY cod_moneda")
        mons = [{"c": r["cod_internacional"], "n": r["nombre_moneda"], "s": r["simbolo"]} for r in c.fetchall()]
        c.execute("SELECT nombre_ocupacion FROM ocupacion ORDER BY cod_ocupacion")
        ocus = [r["nombre_ocupacion"] for r in c.fetchall()]
    return {
        "agencias": ag,
        "totales": {"c": t["clientes"], "a": t["cuentas"], "t": t["tarjetas_activas"]},
        "departamentos": deps,
        "provincias": provs,
        "monedas": mons,
        "ocupaciones": ocus,
    }

def _cuenta(c, numero):
    c.execute("SELECT * FROM vw_cuentas_detalle WHERE numero_cuenta = %s", (numero,))
    return renombrar(c.fetchone(), MAPA_CUENTA)


def _tarjeta(c, numero):
    c.execute("SELECT * FROM vw_tarjetas_detalle WHERE numero_tarjeta = %s", (numero,))
    return renombrar(c.fetchone(), MAPA_TARJETA)


@ruta("POST", r"/api/aperturas")
def apertura(p):  # sp_abrir_cuenta: cliente, teléfono, cuenta y tarjeta en una sola transacción
    a = p.cuerpo
    # "provincia", "calle", "emision_dni" y "peruano_residente" son datos del CLIENTE; "agencia" es la agencia elegida
    # el nombre llega en tres partes (nombres, apellido paterno y apellido materno), como columnas separadas de la tabla cliente
    _requerir(a, ("dni", "nombres", "apellido_paterno", "apellido_materno", "nacimiento", "correo", "telefono", "ocupacion",
                  "provincia", "calle", "emision_dni", "moneda", "agencia"))
    with cur() as c:
        c.execute("SELECT * FROM sp_abrir_cuenta(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (a["dni"], a["nombres"], a["apellido_paterno"], a["apellido_materno"], a["nacimiento"], a["correo"],
                   a["telefono"], a["ocupacion"],
                   a["provincia"], a["calle"], a["emision_dni"], a.get("peruano_residente") is True,
                   a["moneda"], a["agencia"], bool(a.get("tarjeta", True))))
        r = c.fetchone()
        cta = _cuenta(c, r["o_cuenta"])
        tar = _tarjeta(c, r["o_tarjeta"]) if r["o_tarjeta"] else None
    nom = " ".join(str(a[k]).strip() for k in ("nombres", "apellido_paterno", "apellido_materno"))
    return {"nom": nom, "dni": a["dni"], "cta": cta, "tar": tar}


@ruta("GET", r"/api/clientes/(?P<dni>[^/]+)")
def cliente(p, dni):
    with cur() as c:
        c.execute("SELECT * FROM vw_clientes_detalle WHERE dni = %s", (dni,))
        cli = c.fetchone()
        if not cli:
            raise ApiError(404, "Cliente no encontrado")
        c.execute("SELECT * FROM vw_cuentas_detalle WHERE dni = %s ORDER BY numero_cuenta", (dni,))
        cuentas = [renombrar(f, MAPA_CUENTA) for f in c.fetchall()]
        c.execute("SELECT * FROM vw_tarjetas_detalle WHERE dni = %s ORDER BY fecha_emision, numero_tarjeta", (dni,))
        tarjetas = [renombrar(f, MAPA_TARJETA) for f in c.fetchall()]
    return {"cliente": renombrar(cli, MAPA_CLIENTE), "cuentas": cuentas, "tarjetas": tarjetas}


@ruta("POST", r"/api/clientes/(?P<dni>[^/]+)/telefonos")
def agregar_telefono(p, dni):
    _requerir(p.cuerpo, ("telefono",))
    with cur() as c:
        llamar(c, "sp_cliente_agregar_telefono", dni, p.cuerpo["telefono"])
    return {"ok": True}


@ruta("POST", r"/api/cuentas/(?P<num>[^/]+)/estado")
def estado_cuenta(p, num):
    with cur() as c:
        llamar(c, "sp_cuenta_cambiar_estado", num)
    return {"ok": True}


@ruta("POST", r"/api/cuentas/(?P<num>[^/]+)/tarjeta")
def emitir_tarjeta(p, num):
    with cur() as c:
        c.execute("SELECT sp_emitir_tarjeta(%s) AS n", (num,))
        return _tarjeta(c, c.fetchone()["n"])


@ruta("POST", r"/api/tarjetas/(?P<num>[^/]+)/reemplazo")
def reemplazo(p, num):
    with cur() as c:
        c.execute("SELECT sp_reemplazar_tarjeta(%s) AS n", (num,))
        return _tarjeta(c, c.fetchone()["n"])


@ruta("POST", r"/api/agencias/(?P<cod>[^/]+)/estado")
def estado_agencia(p, cod):
    with cur() as c:
        llamar(c, "sp_agencia_cambiar_estado", cod)
    return {"ok": True}


# ---- Reportes: clave -> (título, función almacenada, encabezados). El SQL vive en db/07_reportes.sql
REPORTES = {
    "cuentas": ("Cuentas por cliente", "sp_reporte_cuentas_por_cliente", ["Cliente", "DNI", "N.º de cuenta", "Moneda", "Saldo"]),
    "moneda": ("Cuentas por moneda", "sp_reporte_cuentas_por_moneda", ["Moneda", "Cuentas", "Saldo total"]),
    "agencia": ("Cuentas por agencia", "sp_reporte_cuentas_por_agencia", ["Departamento", "Agencia", "Cuentas"]),
    "varias": ("Clientes con varias cuentas", "sp_reporte_clientes_varias_cuentas", ["Cliente", "DNI", "Total de cuentas"]),
    "inact": ("Tarjetas inactivas", "sp_reporte_tarjetas_inactivas", ["Tarjeta", "Titular", "Cuenta", "Marca", "Emitida", "Vence"]),
    "ocupacion": ("Clientes por ocupación", "sp_reporte_clientes_por_ocupacion", ["Ocupación", "Clientes", "Cuentas"]),
    "departamento": ("Clientes por departamento", "sp_reporte_clientes_por_departamento", ["Departamento", "Provincia", "Clientes"]),
    "marca": ("Tarjetas por marca", "sp_reporte_tarjetas_por_marca", ["Marca", "Activas", "Inactivas", "Total"]),
    "vencer": ("Tarjetas por vencer", "sp_reporte_tarjetas_por_vencer", ["Tarjeta", "Titular", "Marca", "Vence", "Días restantes"]),
    "saldos": ("Mayores saldos por moneda", "sp_reporte_mayores_saldos", ["Moneda", "Puesto", "Cliente", "N.º de cuenta", "Agencia", "Saldo"]),
    "sintarjeta": ("Cuentas sin tarjeta activa", "sp_reporte_cuentas_sin_tarjeta", ["Cliente", "DNI", "N.º de cuenta", "Moneda"]),
}


@ruta("GET", r"/api/reportes")
def reportes_lista(p):
    return [{"k": k, "t": v[0]} for k, v in REPORTES.items()]


@ruta("GET", r"/api/reportes/(?P<k>[^/]+)")
def reporte(p, k):
    if k not in REPORTES:
        raise ApiError(404, "Reporte no existe")
    _, funcion, encabezados = REPORTES[k]
    with cur() as c:
        c.execute("SELECT * FROM " + funcion + "()")
        return {"H": encabezados, "rows": [list(r.values()) for r in c.fetchall()]}


# ---- CRUD: entidad -> vista de listado y procedimientos. Todas las bajas son lógicas.
#   crear / editar = (procedimiento, campos del cuerpo en el orden de sus parámetros); editar recibe primero la clave.
ENT = {
    "clientes": {"lista": "vw_lista_clientes",
                 "crear": ("sp_cliente_crear", ("dni", "nombres", "apellido_paterno", "apellido_materno", "nacimiento", "correo",
                                                "ocupacion", "provincia", "calle", "emision_dni")),
                 "editar": ("sp_cliente_editar", ("nombres", "apellido_paterno", "apellido_materno", "nacimiento", "correo",
                                                 "ocupacion", "provincia", "calle", "emision_dni")),
                 "eliminar": "sp_cliente_eliminar", "activar": "sp_cliente_activar"},
    "agencias": {"lista": "vw_lista_agencias",
                 "crear": ("sp_agencia_crear", ("cod", "nombre", "calle", "provincia", "anexo")),
                 "editar": ("sp_agencia_editar", ("nombre", "calle", "provincia", "anexo")),
                 "eliminar": "sp_agencia_eliminar", "activar": "sp_agencia_activar"},
    "cuentas": {"lista": "vw_lista_cuentas", "crear": None,
                "editar": ("sp_cuenta_editar_tasa", ("tasa",)),
                "eliminar": "sp_cuenta_eliminar", "activar": "sp_cuenta_activar"},
    "tarjetas": {"lista": "vw_lista_tarjetas", "crear": None,
                 "editar": ("sp_tarjeta_editar_marca", ("marca",)),
                 "eliminar": "sp_tarjeta_eliminar", "activar": None},
}


def _ent(e: str, operacion: str):
    if e not in ENT:
        raise ApiError(404, "Entidad no existe")
    if not ENT[e][operacion]:
        raise ApiError(405, "Operación no disponible: usa Nueva apertura" if operacion == "crear" else "Operación no disponible")
    return ENT[e][operacion]


@ruta("GET", r"/api/crud/(?P<e>[^/]+)")
def crud_listar(p, e):
    _ent(e, "lista")
    with cur() as c:
        c.execute("SELECT * FROM " + ENT[e]["lista"])
        return c.fetchall()


@ruta("POST", r"/api/crud/(?P<e>[^/]+)")
def crud_crear(p, e):
    proc, campos = _ent(e, "crear")
    with cur() as c:
        llamar(c, proc, *[p.cuerpo.get(k) for k in campos])
    return {"ok": True}


@ruta("PUT", r"/api/crud/(?P<e>[^/]+)/(?P<key>[^/]+)")
def crud_editar(p, e, key):
    proc, campos = _ent(e, "editar")
    with cur() as c:
        llamar(c, proc, key, *[p.cuerpo.get(k) for k in campos])
    return {"ok": True}


@ruta("DELETE", r"/api/crud/(?P<e>[^/]+)/(?P<key>[^/]+)")
def crud_eliminar(p, e, key):  # baja lógica: el procedimiento pone estado = 0
    with cur() as c:
        llamar(c, _ent(e, "eliminar"), key)
    return {"ok": True}


@ruta("POST", r"/api/crud/(?P<e>[^/]+)/(?P<key>[^/]+)/activar")
def crud_activar(p, e, key):
    with cur() as c:
        llamar(c, _ent(e, "activar"), key)
    return {"ok": True}


@ruta("GET", r"/api/salud")
def salud(p):
    with cur() as c:
        c.execute("SELECT * FROM fn_salud()")
        return c.fetchone()


@ruta("GET", r"/api/ping")
def ping(p):  # permite saber si SAPCUBA ya está abierto
    return {"app": "SAPCUBA"}


@ruta("POST", r"/api/latido")
def latido(p):  # la ventana avisa cada pocos segundos que sigue abierta
    motor_bd.latido()
    return {"ok": True}


@ruta("POST", r"/api/cerrar")
def cerrar(p):  # la ventana avisa que se está cerrando (se cancela si vuelve a enviar latidos)
    origen = p.cabeceras.get("Origin")
    if origen and not ORIGEN_LOCAL.match(origen):
        raise ApiError(403, "Origen no permitido")
    motor_bd.pedir_cierre(30)
    return {"ok": True}


def _solo_exe():
    if not motor_bd.ACTIVO:
        raise ApiError(501, "Los respaldos están disponibles en la aplicación SAPCUBA.exe")


@ruta("GET", r"/api/respaldos")
def respaldos_listar(p):
    _solo_exe()
    return motor_bd.listar()


@ruta("POST", r"/api/respaldos")
def respaldos_crear(p):
    _solo_exe()
    try:
        return motor_bd.respaldar("manual")
    except RuntimeError as e:
        raise ApiError(500, str(e))


@ruta("POST", r"/api/respaldos/restaurar")
def respaldos_restaurar(p):
    _solo_exe()
    try:
        motor_bd.restaurar(str(p.cuerpo.get("nombre", "")))
    except ValueError as e:
        raise ApiError(400, str(e))
    except RuntimeError as e:
        raise ApiError(500, str(e))
    return {"ok": True}


# ----------------------------------------------------------------------------- servidor HTTP
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".png": "image/png", ".ico": "image/x-icon", ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8"}


def _mensaje_bd(e: psycopg2.Error) -> str:
    return {"23503": "No se puede completar: hay registros relacionados.",
            "23505": "Ya existe un registro con ese valor."}.get(e.pgcode) or (e.diag.message_primary if e.diag else None) or "Dato no válido"


class Manejador(BaseHTTPRequestHandler):
    server_version = "SAPCUBA"

    def log_message(self, *args):  # sin ruido en la consola
        pass

    # --- salida
    def _cors(self):
        origen = self.headers.get("Origin", "")
        if ORIGEN_LOCAL.match(origen):  # solo se aceptan peticiones desde esta misma máquina
            self.send_header("Access-Control-Allow-Origin", origen)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _responder(self, estado: int, cuerpo: bytes, tipo: str):
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, estado: int, datos):
        self._responder(estado, json.dumps(datos, default=_serializar, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    # --- entrada
    def _leer_cuerpo(self) -> dict:
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > MAX_CUERPO:
            raise ApiError(413, "Solicitud demasiado grande")
        if largo == 0:
            return {}
        try:
            d = json.loads(self.rfile.read(largo).decode("utf-8"))
        except ValueError:
            raise ApiError(400, "Cuerpo JSON no válido")
        if not isinstance(d, dict):
            raise ApiError(400, "Cuerpo JSON no válido")
        return d

    def _api(self, ruta_: str):
        _ctx.sesion = verificar(ruta_, self.command, self.headers.get("Authorization", ""))
        existe = False
        for metodo, patron, f in RUTAS:
            m = patron.match(ruta_)
            if not m:
                continue
            existe = True
            if metodo == self.command:
                p = Peticion(self.command, ruta_, self.headers, self._leer_cuerpo())
                return self._json(200, f(p, **m.groupdict()))
        raise ApiError(405 if existe else 404, "Método no permitido" if existe else "Ruta no encontrada")

    def _estatico(self, ruta_: str):
        rel = ruta_.lstrip("/")
        if not rel or rel.endswith("/"):
            rel += "index.html"
        destino = os.path.abspath(os.path.join(CARPETA_FRONTEND, rel))
        if os.path.commonpath([destino, CARPETA_FRONTEND]) != CARPETA_FRONTEND or not os.path.isfile(destino):
            raise ApiError(404, "Archivo no encontrado")
        ext = os.path.splitext(destino)[1].lower()
        with open(destino, "rb") as f:
            self._responder(200, f.read(), TIPOS.get(ext) or mimetypes.guess_type(destino)[0] or "application/octet-stream")

    def _atender(self):
        try:
            ruta_ = unquote(urlsplit(self.path).path)
            if ruta_.startswith("/api/"):
                self._api(ruta_)
            elif self.command == "GET":
                self._estatico(ruta_)
            else:
                raise ApiError(405, "Método no permitido")
        except ApiError as e:
            self._json(e.estado, {"detail": e.detalle})
        except psycopg2.OperationalError:
            self._json(503, {"detail": "No hay conexión con la base de datos."})
        except psycopg2.Error as e:  # CHECK, UNIQUE, FK, trigger o RAISE EXCEPTION de un procedimiento: el motor rechaza el dato
            estado = {"P0002": 404, "42501": 403}.get(e.pgcode, 400)  # 42501: el rol no tiene permiso (GRANT)
            self._json(estado, {"detail": "No tienes permiso para esta acción" if e.pgcode == "42501" else _mensaje_bd(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            self._json(500, {"detail": "Error interno del servidor"})

    do_GET = do_POST = do_PUT = do_DELETE = _atender

    def do_OPTIONS(self):  # respuesta a las consultas previas de CORS
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()


def crear_servidor(puerto: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, puerto), Manejador)


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    servidor = crear_servidor(puerto)
    print(f"SAPCUBA en http://localhost:{puerto}  (Ctrl+C para detener)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
