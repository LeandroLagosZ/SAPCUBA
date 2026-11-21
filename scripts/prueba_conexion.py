# Prueba de conexión a la base. Uso: python scripts/prueba_conexion.py
import os, psycopg2
env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env")
if os.path.exists(env):
    os.environ.setdefault("DATABASE_URL", open(env, encoding="utf-8").read().split("DATABASE_URL=")[1].split()[0])
con = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/apertura_cuentas"))
c = con.cursor()
for etiqueta, sql in [("Servidor", "SELECT split_part(version(),',',1)"),
    ("Tablas", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"),
    ("Triggers", "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal"),
    ("Clientes", "SELECT count(*) FROM cliente")]:
    c.execute(sql); print(f"{etiqueta}: {c.fetchone()[0]}")
print("Conexión correcta")
