# Respaldo lógico con pg_dump. Uso: python scripts/respaldo.py
import datetime, glob, os, shutil, subprocess, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = os.path.join(RAIZ, "backend", ".env")
url = os.getenv("DATABASE_URL") or (open(env, encoding="utf-8").read().split("DATABASE_URL=")[1].split()[0] if os.path.exists(env) else None)
if not url:
    sys.exit("Primero ejecuta scripts/crear_base.py")
exe = shutil.which("pg_dump") or next(iter(sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe"), reverse=True)), None)
if not exe:
    sys.exit("No se encontró pg_dump. Usa pgAdmin: clic derecho en la base > Backup...")
os.makedirs(os.path.join(RAIZ, "backups"), exist_ok=True)
destino = os.path.join(RAIZ, "backups", "respaldo_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".backup")
subprocess.run([exe, "-Fc", "-f", destino, url], check=True)
print("Respaldo creado:", destino)
