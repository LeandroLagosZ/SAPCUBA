# Memoria del proyecto · SAPCUBA, Sistema de Apertura de Cuentas
**Integrantes:** Benavente, Calle, Lagos, Quiroz.

## 1. Introducción y objetivo
Automatizar la apertura de Cuentas de Ahorros Movibles, hoy apoyada en documentos físicos, con una base de datos centralizada y un aplicativo web.

## 2. Diseño de datos (resumen del informe)
Modelo Entidad-Relación → modelo relacional normalizado (3FN) → modelo físico en PostgreSQL con 9 tablas del negocio (`departamento`, `provincia`, `ocupacion`, `moneda`, `agencia`, `cliente`, `telefono_clientes`, `cuenta_ahorros`, `tarjeta`) y sin tablas de usuarios ni de auditoría (el acceso usa los roles del motor). Incluye claves, restricciones CHECK (DNI 8 dígitos, CCI 20, tarjeta 16, CVV 3) e índices en claves foráneas.

## 3. Arquitectura
PostgreSQL 16 · servidor HTTP de Python sin frameworks (`http.server`) · interfaz HTML/JS. Se distribuye como un único ejecutable `SAPCUBA.exe` que incluye PostgreSQL portátil: al abrirlo crea la base en la carpeta del usuario, inicia el servidor local y muestra el sistema en una ventana propia; al cerrarla, hace un respaldo y apaga el motor. Para desarrollo también puede ejecutarse con `scripts/crear_base.py` y `python backend/main.py`.

## 4. Implementación
**CRUD:** clientes, agencias, cuentas (se crean con la apertura), tarjetas (se emiten desde la cuenta). Todas las escrituras se hacen con procedimientos almacenados (`CALL sp_cliente_crear`, `sp_cliente_editar`, `sp_cliente_eliminar`, etc.) y las bajas son **lógicas** (`estado = 0`, con opción de reactivar); el backend no ejecuta `INSERT`, `UPDATE` ni `DELETE`.

**Procedimientos almacenados:** `sp_abrir_cuenta`, `sp_emitir_tarjeta`, `sp_reemplazar_tarjeta` y los procedimientos del CRUD (`sp_cliente_*`, `sp_agencia_*`, `sp_cuenta_*`, `sp_tarjeta_*`).

**Vistas:** `vw_clientes_detalle`, `vw_cuentas_detalle`, `vw_tarjetas_detalle`, `vw_lista_clientes`, `vw_lista_agencias`, `vw_lista_cuentas`, `vw_lista_tarjetas` y `vw_totales`.

**Reportes (11, funciones `sp_reporte_*`, 10 con JOIN):** cuentas por cliente, por moneda y por agencia; clientes con varias cuentas; tarjetas inactivas; clientes por ocupación y por departamento; tarjetas por marca; tarjetas por vencer; mayores saldos por moneda; cuentas sin tarjeta activa.

**Triggers:** reglas de negocio, sin tabla de auditoría: `trg_validar_cuenta` (agencia, moneda y cliente activos), `trg_cuenta_inmutable` (no cambian número, CCI, contrato, titular ni moneda), `trg_validar_tarjeta` (cuenta activa), `trg_tarjeta_reactivar` (no se reactiva una tarjeta de cuenta inactiva) y `trg_cuenta_inactiva` (inactiva las tarjetas al desactivar la cuenta).

**Seguridad:** el inicio de sesión usa las credenciales del motor PostgreSQL (la aplicación se conecta con el usuario y la contraseña escritos, y PostgreSQL los valida). Dos grupos de roles, `sapcuba_admin` y `sapcuba_agente` (`db/08_roles.sql`), con sus `GRANT`: el motor aplica los permisos porque cada petición corre con la conexión del usuario. La sesión dura 8 horas.

**Transacciones:** la apertura guarda cliente, teléfono, cuenta y tarjeta como una sola operación.

## 5. Pruebas
Prueba de conexión (`scripts/prueba_conexion.py` y botón en Administración), pruebas de cada CRUD desde la interfaz y casos de rechazo (DNI inválido, agencia inactiva, dar de baja a un cliente con cuentas activas) y `scripts/probar_bd.py`, que ejecuta todas las vistas, reportes y procedimientos.
*(Adjuntar capturas de pantalla de cada prueba.)*

## 6. Respaldo y recuperación
Implementado en la aplicación: copia lógica con `pg_dump` (formato personalizado) de tres tipos: **automática** al cerrar el programa (se conservan los 10 últimos), **manual** desde Administración y **de seguridad** justo antes de cada restauración. La restauración (`pg_restore`, en una sola transacción) devuelve la base a un respaldo elegido; si falla, los datos actuales no se modifican. Los archivos `.backup` se guardan en `Documentos\SAPCUBA\Respaldos` y pueden copiarse a otra computadora.
Quedan como mejora para un entorno de producción la copia física periódica y el archivado WAL (RPO 5 min, RTO 2 h del informe), que requieren un servidor PostgreSQL dedicado.

## 7. Conclusiones
*(Completar con las conclusiones del equipo.)*

## Anexos
Script completo (`docs/script_completo.sql`), código fuente (carpetas `backend/` y `frontend/`) y manual de usuario (`docs/MANUAL_DE_USUARIO.md`).
