# Crea la base de datos y ejecuta los scripts de la carpeta db/ (01 al 08).
# Uso (desde la carpeta del proyecto, con el entorno virtual activo): python scripts/crear_base.py
import getpass, glob, os, sys
from urllib.parse import quote_plus
import psycopg2

EMPAQUETADO = getattr(sys, "frozen", False)  # True cuando corre como CrearBase.exe
if EMPAQUETADO:
    CARPETA_DB = os.path.join(sys._MEIPASS, "db")
    ARCHIVO_ENV = os.path.join(os.path.dirname(sys.executable), ".env")  # junto al .exe
else:
    RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CARPETA_DB = os.path.join(RAIZ, "db")
    ARCHIVO_ENV = os.path.join(RAIZ, "backend", ".env")
BD = "apertura_cuentas"


def main():
    host = input("Servidor [localhost]: ").strip() or "localhost"
    puerto = input("Puerto [5432]: ").strip() or "5432"
    usuario = input("Usuario [postgres]: ").strip() or "postgres"
    clave = getpass.getpass("Contraseña de PostgreSQL (no se ve al escribir): ")

    try:
        con = psycopg2.connect(host=host, port=puerto, user=usuario, password=clave, dbname="postgres")
    except psycopg2.Error as e:
        sys.exit("No se pudo conectar: " + str(e).strip())
    con.autocommit = True
    cur = con.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (BD,))
    if cur.fetchone():
        if input(f"La base {BD} ya existe. ¿Borrarla y crearla de nuevo? (s/n): ").lower() != "s":
            sys.exit("Cancelado.")
        cur.execute(f'DROP DATABASE "{BD}" WITH (FORCE)')
    cur.execute(f'CREATE DATABASE "{BD}"')
    con.close()

    con = psycopg2.connect(host=host, port=puerto, user=usuario, password=clave, dbname=BD)
    cur = con.cursor()
    for f in sorted(glob.glob(os.path.join(CARPETA_DB, "0*.sql"))):
        print("Ejecutando", os.path.basename(f))
        cur.execute(open(f, encoding="utf-8").read())
    con.commit()
    url = f"postgresql://{quote_plus(usuario)}:{quote_plus(clave)}@{host}:{puerto}/{BD}"
    open(ARCHIVO_ENV, "w", encoding="utf-8").write(f"DATABASE_URL={url}\n")
    print("Listo: base creada y conexión guardada en", ARCHIVO_ENV)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code:
            print(e.code)
    except Exception as e:
        print("Error:", str(e).strip())
    if EMPAQUETADO:
        input("\nPresiona Enter para cerrar...")
