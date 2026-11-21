# SAPCUBA · Sistema de Apertura de Cuentas

Aplicación de escritorio para Windows: **un solo archivo `SAPCUBA.exe`**. Doble clic y listo: no hay que instalar PostgreSQL, Python ni Docker.
Por dentro usa **PostgreSQL 16 (incluido) + servidor HTTP de Python (librería estándar, sin frameworks) + HTML/JS**.

## Usar SAPCUBA.exe
1. Doble clic en `SAPCUBA.exe`. Aparece una ventana de espera ("Iniciando…"); la **primera vez** tarda cerca de un minuto porque crea la base de datos. Después abre en unos segundos.
2. Se abre la ventana del sistema. Ingresa con un usuario de PostgreSQL (el sistema no tiene tabla propia de usuarios). Usuarios de prueba:

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `Admin123` | Administrador (`sapcuba_admin`): todo, incluye respaldos, agencias, bajas y activaciones |
| `agente` | `Agente123` | Agente (`sapcuba_agente`): aperturas, consultas, edición y reportes |

3. Para salir, **cierra la ventana**. SAPCUBA guarda un respaldo automático y se apaga solo.

**Dónde quedan tus datos** (no se pierden al actualizar el .exe):
- Base de datos: `C:\Users\TU_USUARIO\AppData\Local\SAPCUBA\`
- Respaldos: `Documentos\SAPCUBA\Respaldos\` (archivos `.backup`)

**Más usuarios:** se crean en PostgreSQL, no en la aplicación. Con un superusuario: `CREATE ROLE maria LOGIN PASSWORD '...' IN ROLE sapcuba_agente;` (o `sapcuba_admin`). Para cambiar una clave: `ALTER ROLE agente PASSWORD '...';`.

**Respaldos** (menú *Administración*, solo administrador): *Generar respaldo ahora*, y *Restaurar* sobre cualquier respaldo de la lista. Antes de restaurar, SAPCUBA guarda una copia de los datos actuales. Se conservan los últimos 10 respaldos automáticos. Para llevar tus datos a otra computadora: copia el `.backup` a la carpeta de respaldos de la otra PC y restáuralo allí.

**Si Windows lo bloquea:** SmartScreen o el antivirus pueden avisar porque el programa no está firmado. Elige *Más información > Ejecutar de todas formas*.
**Si algo falla**, el detalle queda en `AppData\Local\SAPCUBA\sapcuba.log`.

## Construir SAPCUBA.exe (una vez, en Windows)
Requisitos para recompilar: **Python 3.12 o 3.13 de 64 bits** (marca *Add Python to PATH*) e Internet. No uses Python 3.14 con `psycopg2-binary==2.9.10`, porque todavía no dispone de una rueda compatible y la instalación intentará compilar código C.
Doble clic en **`construir_exe.bat`**. Descarga PostgreSQL portátil, empaqueta todo y deja el resultado en `salida\SAPCUBA.exe` (≈ 60–90 MB). Ese único archivo es el que se entrega o se copia a otras PC.

## Ejecutar desde el código (desarrollo)
Necesita PostgreSQL 16 instalado y Python 3.10+.
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cd ..
python scripts/crear_base.py    # pide servidor, puerto, usuario y contraseña de PostgreSQL
cd backend
python main.py
```
Abre **http://localhost:8000**. Para comprobar toda la base (vistas, 11 reportes y todos los procedimientos; no deja datos): `python scripts/probar_bd.py`.
**Alternativa manual (pgAdmin):** crea la base `apertura_cuentas`, ejecuta `docs/script_completo.sql` y crea `backend/.env` con `DATABASE_URL=postgresql://postgres:TU_CLAVE@localhost:5432/apertura_cuentas` (la aplicación solo toma de ahí el servidor, el puerto y la base; al iniciar sesión usa el usuario y la clave que escribas). Las pruebas y respaldos por script sí usan el usuario de ese `DATABASE_URL`.
En este modo los respaldos se hacen con `python scripts/respaldo.py` (guarda en `backups/`).

## Seguridad
- **Autenticación con el motor:** el usuario y la contraseña de la pantalla de acceso se usan para conectarse a PostgreSQL; PostgreSQL valida la clave (SCRAM). No hay tabla de usuarios ni contraseñas en la base.
- **Roles y permisos en el motor:** `db/08_roles.sql` crea los grupos `sapcuba_admin` y `sapcuba_agente` y sus `GRANT`. Cada petición se ejecuta con la conexión del usuario que inició sesión, así que el motor rechaza lo que su rol no puede hacer (el servidor además oculta esas acciones). El agente no puede dar de baja, activar ni tocar agencias; nadie tiene `DELETE`.
- **Sesión:** dura 8 horas. El navegador solo guarda un token aleatorio; la contraseña queda en la memoria del servidor y se olvida al cerrar sesión.
- **Reglas de negocio:** las hacen cumplir los triggers de `db/05_triggers.sql` (no hay tabla de auditoría).
- En SAPCUBA.exe la base de datos escucha solo en esta computadora (127.0.0.1) y la clave interna de `postgres` se genera al azar. **Cambia las contraseñas de prueba (`ALTER ROLE`) antes de usarlo fuera de clase.**
- **Si actualizas desde la versión anterior**, SAPCUBA.exe migra la base solo al abrirla (`db/migracion/`): elimina las tablas `usuario` y `auditoria` y crea los roles. Un respaldo `.backup` de la versión anterior se migra igual en el siguiente inicio.

## Carpetas y responsables
| Carpeta | Contenido | Persona |
|---|---|---|
| `db/` | Tablas, índices, datos, procedimientos (04), triggers (05), vistas (06), reportes (07) y roles de acceso (08) | 1 |
| `backend/` | Servidor HTTP sin frameworks (`main.py`), motor de base de datos y respaldos (`motor_bd.py`), arranque del .exe (`sapcuba.py`) | 2 |
| `frontend/` | Pantallas, botones e inicio de sesión | 3 |
| `docs/`, `scripts/` | Script completo, memoria, manual, utilidades y construcción | 4 |

DNI de prueba: `60967097` y `45120388`.

## Cómo se organiza el acceso a datos (Entrega 5)
- **Sin frameworks:** `backend/main.py` usa solo `http.server` de la librería estándar; `psycopg2` es el conector a PostgreSQL.
- **Sin SQL de negocio en Python:** el backend no contiene `INSERT`, `UPDATE` ni `DELETE`. Las escrituras son `CALL sp_...` (procedimientos de `db/04_procedimientos.sql`), los reportes son `SELECT * FROM sp_reporte_...()` (`db/07_reportes.sql`) y las lecturas pasan por vistas `vw_...` (`db/06_vistas.sql`).
- **Reportes:** 11, de los cuales 10 usan JOIN explícito.
- **Bajas lógicas:** eliminar un registro solo pone `estado = 0`; el administrador puede volver a activarlo. No se borra ninguna fila.
