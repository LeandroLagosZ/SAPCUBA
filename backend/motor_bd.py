"""Motor de base de datos de SAPCUBA.

Incluye un PostgreSQL portátil dentro del .exe: la primera vez crea la base de datos en la carpeta del usuario,
las siguientes solo la inicia. También genera y restaura respaldos (pg_dump / pg_restore) y controla el ciclo de
vida de la aplicación (latidos de la ventana para cerrarse sola).
"""
import glob, os, secrets, shutil, socket, subprocess, sys, tempfile, threading, time
from datetime import datetime

import psycopg2

NOMBRE = "SAPCUBA"
BD = "apertura_cuentas"
EMPAQUETADO = getattr(sys, "frozen", False)
RECURSOS = sys._MEIPASS if EMPAQUETADO else os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PG = os.environ.get("SAPCUBA_PG") or os.path.join(RECURSOS, "pginstall")

ACTIVO = False   # True mientras el PostgreSQL incluido está funcionando
PUERTO = 0
CLAVE = ""
_CREATE_NO_WINDOW = 0x08000000


def _carpeta_documentos() -> str:
    if os.name == "nt":
        try:  # carpeta "Documentos" real (puede estar en OneDrive)
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return buf.value
        except Exception:
            pass
    doc = os.path.join(os.path.expanduser("~"), "Documents")
    return doc if os.path.isdir(doc) else os.path.expanduser("~")


def _carpeta_datos() -> str:
    if os.name == "nt":
        raiz = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        raiz = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(raiz, NOMBRE)


DATOS = os.environ.get("SAPCUBA_DATOS") or _carpeta_datos()
PGDATA = os.path.join(DATOS, "pgdata")
LOG_PG = os.path.join(DATOS, "postgres.log")
RESPALDOS = os.environ.get("SAPCUBA_RESPALDOS") or os.path.join(_carpeta_documentos(), NOMBRE, "Respaldos")

# --- Ciclo de vida: la ventana envía "latidos"; si deja de enviarlos o avisa que se cerró, la app termina ---
CICLO = {"latido": time.time(), "visto": False, "cerrar_en": None}


def latido():
    CICLO.update(latido=time.time(), visto=True, cerrar_en=None)


def pedir_cierre(segundos: float = 10):
    CICLO["cerrar_en"] = time.time() + segundos


# --- Utilidades ---
def _exe(nombre: str) -> str:
    return os.path.join(PG, "bin", nombre + (".exe" if os.name == "nt" else ""))


def _correr(args, env=None, timeout=300):
    """Ejecuta un programa de PostgreSQL sin ventana. Usa archivos temporales (las tuberías pueden colgar a pg_ctl en Windows)."""
    e = dict(os.environ)
    if env:
        e.update(env)
    kw = {"creationflags": _CREATE_NO_WINDOW} if os.name == "nt" else {}
    with tempfile.TemporaryFile("w+b") as f:
        p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, env=e, timeout=timeout, **kw)
        f.seek(0)
        return p.returncode, f.read().decode("utf-8", "replace").strip()


def puerto_libre(inicio: int, fin: int = 0) -> int:
    for p in range(inicio, (fin or inicio + 200)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError("No hay un puerto libre disponible.")


def _conectar(bd: str):
    return psycopg2.connect(host="127.0.0.1", port=PUERTO, user="postgres", password=CLAVE, dbname=bd, connect_timeout=10)


def _puerto_en_marcha():
    """Si PostgreSQL ya está corriendo con nuestros datos (cierre anormal anterior), devuelve su puerto."""
    code, _ = _correr([_exe("pg_ctl"), "status", "-D", PGDATA])
    if code != 0:
        return None
    try:
        with open(os.path.join(PGDATA, "postmaster.pid"), encoding="utf-8") as f:
            return int(f.read().splitlines()[3])
    except Exception:
        return None


# --- Inicio / cierre ---
def iniciar(progreso=lambda m: None):
    global ACTIVO, PUERTO, CLAVE
    if not os.path.isfile(_exe("postgres")):
        raise RuntimeError("Falta el motor PostgreSQL incluido en la aplicación (carpeta pginstall).")
    os.makedirs(DATOS, exist_ok=True)
    archivo_clave = os.path.join(DATOS, "bd.clave")

    if not os.path.isfile(os.path.join(PGDATA, "PG_VERSION")):
        progreso("Preparando la base de datos (solo la primera vez, puede tardar un minuto)...")
        CLAVE = secrets.token_urlsafe(24)
        shutil.rmtree(PGDATA, ignore_errors=True)
        archivo_pw = os.path.join(DATOS, "pw.tmp")
        with open(archivo_pw, "w", encoding="utf-8") as f:
            f.write(CLAVE)
        try:
            code, salida = _correr([_exe("initdb"), "-D", PGDATA, "-U", "postgres", "-A", "scram-sha-256",
                                    "--pwfile", archivo_pw, "-E", "UTF8", "--no-locale"], timeout=600)
        finally:
            os.remove(archivo_pw)
        if code != 0:
            shutil.rmtree(PGDATA, ignore_errors=True)
            raise RuntimeError("No se pudo crear la base de datos:\n" + salida[-800:])
        with open(archivo_clave, "w", encoding="utf-8") as f:
            f.write(CLAVE)
    else:
        with open(archivo_clave, encoding="utf-8") as f:
            CLAVE = f.read().strip()

    progreso("Iniciando la base de datos...")
    PUERTO = _puerto_en_marcha() or 0
    if not PUERTO:
        PUERTO = puerto_libre(54329)
        opciones = f"-h 127.0.0.1 -p {PUERTO}"
        if os.name != "nt":
            opciones += f" -k {DATOS}"
        code, salida = _correr([_exe("pg_ctl"), "start", "-w", "-t", "90", "-D", PGDATA, "-l", LOG_PG, "-o", opciones], timeout=150)
        if code != 0:
            raise RuntimeError("No se pudo iniciar PostgreSQL:\n" + salida[-800:])
    ACTIVO = True

    # Crear la base y cargar las tablas, procedimientos y datos la primera vez
    con = _conectar("postgres")
    con.autocommit = True
    with con.cursor() as c:
        c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (BD,))
        if not c.fetchone():
            c.execute(f'CREATE DATABASE "{BD}" ENCODING \'UTF8\' TEMPLATE template0')
    con.close()
    con = _conectar(BD)
    with con.cursor() as c:
        c.execute("SELECT to_regclass('public.cliente'), to_regclass('public.usuario'), to_regclass('public.auditoria')")
        hay_cliente, hay_usuario, hay_auditoria = c.fetchone()
        if hay_cliente is None:
            progreso("Creando tablas y datos iniciales...")
            for f in sorted(glob.glob(os.path.join(RECURSOS, "db", "0*.sql"))):
                with open(f, encoding="utf-8") as fh:
                    c.execute(fh.read())
            con.commit()
        else:  # base de una versión anterior: aplicar las migraciones que falten y recargar procedimientos, triggers, vistas y roles
            c.execute("SELECT data_type FROM information_schema.columns "
                      "WHERE table_name = 'tarjeta' AND column_name = 'codigo_tarjeta' AND table_schema = 'public'")
            fila = c.fetchone()
            pasos = []
            if fila and fila[0] == "smallint":  # CVV numérico: pasar a texto de 3 dígitos
                pasos.append("migracion/cvv_y_tasa.sql")
            if hay_usuario or hay_auditoria:    # tablas usuario/auditoría: migrar a roles de PostgreSQL
                pasos.append("migracion/desde_auditoria_y_usuarios.sql")
            c.execute("SELECT 1 FROM information_schema.columns "
                      "WHERE table_name = 'cliente' AND column_name = 'fecha_emision_dni' AND table_schema = 'public'")
            if c.fetchone() is None:            # cliente sin calle obligatoria, emisión del DNI ni confirmación de residencia
                pasos.append("migracion/direccion_y_dni.sql")
            c.execute("SELECT 1 FROM information_schema.columns "
                      "WHERE table_name = 'cliente' AND column_name = 'nombres_completos' AND table_schema = 'public'")
            if c.fetchone() is not None:        # nombre en una sola columna y calle de 80: separar nombres/apellidos y ampliar a 100
                pasos.append("migracion/nombres_y_calle.sql")
            if pasos:
                progreso("Actualizando la base de datos...")
                if hay_usuario or hay_auditoria:  # la migración borró los triggers viejos: se crean de nuevo
                    pasos.append("05_triggers.sql")
                pasos += ["04_procedimientos.sql", "06_vistas.sql", "07_reportes.sql", "08_roles.sql"]
                for nombre in pasos:
                    with open(os.path.join(RECURSOS, "db", nombre), encoding="utf-8") as fh:
                        c.execute(fh.read())
                con.commit()
    con.close()

    # Solo se publica el servidor, el puerto y la base: el usuario y la contraseña con que trabaja la aplicación
    # son los de quien inicia sesión (roles de PostgreSQL). La cuenta interna "postgres" se usa solo para los respaldos.
    os.environ["DATABASE_URL"] = f"postgresql://127.0.0.1:{PUERTO}/{BD}"


def cerrar():
    """Respaldo automático y apagado ordenado de PostgreSQL."""
    global ACTIVO
    if not ACTIVO:
        return
    try:
        respaldar("auto")
    except Exception:
        pass
    _correr([_exe("pg_ctl"), "stop", "-D", PGDATA, "-m", "fast", "-w", "-t", "60"], timeout=90)
    ACTIVO = False


# --- Respaldos ---
def _info(ruta: str) -> dict:
    st, base = os.stat(ruta), os.path.basename(ruta)
    return {"nombre": base, "kb": max(1, round(st.st_size / 1024)),
            "fecha": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
            "tipo": "Automático" if "_auto." in base else "Antes de restaurar" if "_antes." in base else "Manual"}


def listar() -> dict:
    archivos = sorted(glob.glob(os.path.join(RESPALDOS, "SAPCUBA_*.backup")), key=os.path.getmtime, reverse=True)
    return {"carpeta": RESPALDOS, "items": [_info(a) for a in archivos]}


def respaldar(motivo: str = "manual") -> dict:
    if not ACTIVO:
        raise RuntimeError("Los respaldos solo están disponibles en la aplicación SAPCUBA.exe.")
    os.makedirs(RESPALDOS, exist_ok=True)
    ruta = os.path.join(RESPALDOS, f"SAPCUBA_{datetime.now():%Y-%m-%d_%H-%M-%S}_{motivo}.backup")
    code, salida = _correr([_exe("pg_dump"), "-h", "127.0.0.1", "-p", str(PUERTO), "-U", "postgres", "-d", BD, "-F", "c", "-f", ruta],
                           env={"PGPASSWORD": CLAVE})
    if code != 0:
        if os.path.exists(ruta):
            os.remove(ruta)
        raise RuntimeError("No se pudo crear el respaldo:\n" + salida[-500:])
    for viejo in sorted(glob.glob(os.path.join(RESPALDOS, "SAPCUBA_*_auto.backup")), key=os.path.getmtime, reverse=True)[10:]:
        os.remove(viejo)  # se conservan los últimos 10 automáticos
    return _info(ruta)


def restaurar(nombre: str) -> None:
    if not ACTIVO:
        raise RuntimeError("La restauración solo está disponible en la aplicación SAPCUBA.exe.")
    if os.path.basename(nombre) != nombre or not nombre.endswith(".backup"):
        raise ValueError("Nombre de respaldo no válido.")
    ruta = os.path.join(RESPALDOS, nombre)
    if not os.path.isfile(ruta):
        raise ValueError("El respaldo no existe.")
    respaldar("antes")  # copia de seguridad del estado actual, por si algo sale mal
    code, salida = _correr([_exe("pg_restore"), "-h", "127.0.0.1", "-p", str(PUERTO), "-U", "postgres", "-d", BD,
                            "--clean", "--if-exists", "--no-owner", "--single-transaction", ruta], env={"PGPASSWORD": CLAVE})
    if code != 0:
        raise RuntimeError("No se pudo restaurar (los datos actuales no se modificaron):\n" + salida[-500:])
