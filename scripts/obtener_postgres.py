# Descarga un PostgreSQL 16 portátil (paquete "pgserver" de PyPI) y deja la carpeta "pginstall" lista
# para incluirla dentro de SAPCUBA.exe. Se ejecuta una sola vez al construir (construir_exe.bat).
import glob, os, shutil, subprocess, sys, tempfile, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "pginstall")
PAQUETE = "pgserver==0.1.4"  # PostgreSQL 16

if os.path.isfile(os.path.join(DESTINO, "bin", "initdb.exe" if os.name == "nt" else "initdb")):
    print("PostgreSQL portátil ya está en", DESTINO)
    sys.exit(0)

if sys.platform.startswith("win"):
    plataformas = ["win_amd64"]
elif sys.platform == "darwin":
    plataformas = ["macosx_11_0_arm64"]
else:
    plataformas = ["manylinux2014_x86_64", "manylinux_2_17_x86_64"]

tmp = tempfile.mkdtemp()
try:
    print("Descargando", PAQUETE, "...")
    cmd = [sys.executable, "-m", "pip", "download", PAQUETE, "--no-deps", "--only-binary=:all:",
           "--python-version", "3.12", "-d", tmp]
    for p in plataformas:
        cmd += ["--platform", p]
    r = subprocess.run(cmd)
    ruedas = glob.glob(os.path.join(tmp, "*.whl"))
    if r.returncode or not ruedas:
        sys.exit("No se pudo descargar PostgreSQL portátil. Revisa tu conexión a Internet y vuelve a intentar.")
    print("Extrayendo ...")
    # En Linux/macOS el paquete trae además "pgserver.libs" (librerías compartidas); en Windows no hace falta.
    carpetas = {"pgserver/pginstall/": DESTINO, "pgserver.libs/": os.path.join(RAIZ, "pgserver.libs")}
    with zipfile.ZipFile(ruedas[0]) as z:
        for info in z.infolist():
            for prefijo, base in carpetas.items():
                if not info.filename.startswith(prefijo) or info.is_dir():
                    continue
                destino = os.path.join(base, info.filename[len(prefijo):])
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with z.open(info) as o, open(destino, "wb") as f:
                    shutil.copyfileobj(o, f)
                if os.name != "nt" and ("/bin/" in info.filename or ".so" in info.filename):
                    os.chmod(destino, 0o755)
    print("Listo:", DESTINO)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
