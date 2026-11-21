"""SAPCUBA - Sistema de Apertura de Cuentas.  Punto de entrada del .exe (doble clic y listo).

Qué hace: inicia el PostgreSQL incluido, levanta el servidor HTTP interno, abre la ventana del sistema y,
al cerrar la ventana, hace un respaldo automático y apaga todo ordenadamente.
"""
import os, shutil, sys, threading, time, urllib.request, webbrowser

import motor_bd

TITULO = "Sistema de Apertura de Cuentas SAPCUBA"
PUERTOS = range(8000, 8011)


def mensaje_error(texto: str):
    print("ERROR:", texto)
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, texto, "SAPCUBA - Error", 0x10)
        except Exception:
            pass


def hay_sapcuba(puerto: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/ping", timeout=0.7) as r:
            return b"SAPCUBA" in r.read()
    except Exception:
        return False


def abrir_ventana(url: str):
    """Abre el sistema como ventana de aplicación (Edge o Chrome sin barra de direcciones). Devuelve el proceso o None."""
    import subprocess
    cand = []
    if os.name == "nt":
        for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                cand += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                         os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    else:
        cand = [shutil.which(n) for n in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser")]
    for exe in cand:
        if exe and os.path.isfile(exe):
            try:
                return subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={os.path.join(motor_bd.DATOS, 'perfil_web')}",
                                         "--window-size=1280,860", "--no-first-run", "--no-default-browser-check",
                                         "--disable-background-mode"])
            except Exception:
                pass
    webbrowser.open(url)  # sin Edge/Chrome: navegador predeterminado
    return None


def trabajo(est: dict):
    try:
        os.makedirs(motor_bd.DATOS, exist_ok=True)
        if getattr(sys, "frozen", False):  # sin consola: todo lo que se imprima va a un archivo de registro
            sys.stdout = sys.stderr = open(os.path.join(motor_bd.DATOS, "sapcuba.log"), "a", encoding="utf-8", buffering=1)
        for p in PUERTOS:  # si ya está abierto, solo traer la ventana
            if hay_sapcuba(p):
                abrir_ventana(f"http://localhost:{p}")
                return
        motor_bd.iniciar(lambda m: est.update(msg=m))
        est["msg"] = "Iniciando el sistema..."
        import main  # servidor HTTP propio (librería estándar); se importa después de iniciar PostgreSQL
        puerto = motor_bd.puerto_libre(8000, 8011)
        servidor = main.crear_servidor(puerto)
        hilo = threading.Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
        hilo.start()
        inicio = time.time()
        motor_bd.latido()
        motor_bd.CICLO["visto"] = False
        proc = abrir_ventana(f"http://localhost:{puerto}")
        est["cerrar_splash"] = True
        if proc is not None:  # al cerrar la ventana de la aplicación, cerrar todo (si no fue un arranque fallido)
            def espera():
                proc.wait()
                if time.time() - inicio > 8:
                    motor_bd.pedir_cierre(3)
            threading.Thread(target=espera, daemon=True).start()
        while True:  # vigilante: termina cuando la ventana se cierra
            time.sleep(1)
            c, ahora = motor_bd.CICLO, time.time()
            if c["cerrar_en"] and ahora >= c["cerrar_en"]:
                break
            if c["visto"] and ahora - c["latido"] > 180:
                break
            if not c["visto"] and ahora - inicio > 300:
                break
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=10)
    except Exception as e:
        mensaje_error(f"No se pudo iniciar SAPCUBA.\n\n{e}\n\nRegistro: {os.path.join(motor_bd.DATOS, 'sapcuba.log')}")
    finally:
        est["msg"] = "Guardando respaldo y cerrando..."
        try:
            motor_bd.cerrar()
        except Exception as e:
            print("Error al cerrar:", e)
        est["cerrar_splash"] = True


def main():
    est = {"msg": "Iniciando...", "cerrar_splash": False}
    hilo = threading.Thread(target=trabajo, args=(est,))
    hilo.start()
    try:  # ventanita de espera mientras arranca (la primera vez tarda más)
        import tkinter as tk
        from tkinter import ttk
        raiz = tk.Tk()
        raiz.title("SAPCUBA")
        raiz.resizable(False, False)
        raiz.protocol("WM_DELETE_WINDOW", lambda: None)
        w, h = 420, 170
        raiz.geometry(f"{w}x{h}+{(raiz.winfo_screenwidth() - w) // 2}+{(raiz.winfo_screenheight() - h) // 3}")
        raiz.attributes("-topmost", True)
        tk.Label(raiz, text="SAPCUBA", font=("Segoe UI", 22, "bold"), fg="#0e7c7b").pack(pady=(18, 0))
        tk.Label(raiz, text="Sistema de Apertura de Cuentas", font=("Segoe UI", 10)).pack()
        texto = tk.StringVar(value=est["msg"])
        tk.Label(raiz, textvariable=texto, font=("Segoe UI", 9), wraplength=380).pack(pady=(12, 6))
        barra = ttk.Progressbar(raiz, mode="indeterminate", length=340)
        barra.pack()
        barra.start(12)

        def revisar():
            texto.set(est["msg"])
            if est["cerrar_splash"]:
                raiz.destroy()
            else:
                raiz.after(200, revisar)
        raiz.after(200, revisar)
        raiz.mainloop()
    except Exception:
        pass
    hilo.join()


if __name__ == "__main__":
    main()
