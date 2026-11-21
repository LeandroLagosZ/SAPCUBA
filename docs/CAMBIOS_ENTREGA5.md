# Correcciones para la Entrega 5

| Observación | Qué se hizo | Dónde |
|---|---|---|
| Usa FastAPI (framework) | Se eliminó FastAPI, Uvicorn y Pydantic. El servidor usa solo `http.server` de la librería estándar. Queda solo `psycopg2` (conector). | `backend/main.py`, `backend/sapcuba.py`, `requirements.txt` |
| Solo 5 reportes (mínimo 10, 6 con JOIN) | Ahora hay **11 reportes**, **10 con JOIN** (el de tarjetas por marca usa una sola tabla). | `db/07_reportes.sql` |
| Los reportes ejecutan SQL desde Python | Cada reporte es una función almacenada `sp_reporte_*`; Python solo ejecuta `SELECT * FROM sp_reporte_x()`. | `db/07_reportes.sql`, `REPORTES` en `main.py` |
| CRUD con INSERT/UPDATE/DELETE directos | Todo el CRUD usa procedimientos (`CALL sp_cliente_crear(...)`, etc.). Python ya no contiene `INSERT`, `UPDATE` ni `DELETE`. | `db/04_procedimientos.sql`, `ENT` en `main.py` |
| Borrados físicos | Todas las bajas son lógicas: el procedimiento pone `estado = 0`. Hay procedimientos `*_activar` para revertirlas. Ninguna fila se borra. | `db/04_procedimientos.sql`, botones «Dar de baja» / «Activar» |
| Sin vistas | 8 vistas `vw_*`; el backend lee siempre a través de ellas. | `db/06_vistas.sql` |
| Solo 3 procedimientos | Los 3 originales más 20 procedimientos del CRUD (clientes, agencias, cuentas, tarjetas) y 11 funciones de reporte. | `db/04_procedimientos.sql`, `db/07_reportes.sql` |

Prueba: `python scripts/probar_bd.py` ejecuta todas las vistas, reportes y procedimientos en una transacción que se deshace.

## Sin tablas nuevas: acceso con los roles de PostgreSQL
| Observación | Qué se hizo | Dónde |
|---|---|---|
| `auditoria` era una tabla nueva | Se eliminó la tabla, su función y sus 3 triggers, la vista y la pantalla. Las reglas del negocio quedan en triggers de validación. | `db/05_triggers.sql` |
| `usuario` era una tabla nueva | Se eliminó la tabla, sus procedimientos, la vista, el CRUD y `bcrypt`. El inicio de sesión se conecta a PostgreSQL con el usuario y la contraseña escritos. | `db/08_roles.sql`, `backend/main.py` |
| Roles ADMIN / AGENTE | Son grupos de PostgreSQL (`sapcuba_admin`, `sapcuba_agente`) con `GRANT`; el motor rechaza lo que el rol no puede. | `db/08_roles.sql` |
| Bases ya creadas | Se migran solas al abrir la aplicación. | `db/migracion/` |

## Observaciones menores corregidas
| Observación | Qué se hizo | Dónde |
|---|---|---|
| El CVV (`SMALLINT`) perdía los ceros iniciales | Ahora es `CHAR(3)` con `CHECK` de 3 dígitos (`007` se conserva). | `db/01_tablas.sql`, `db/04_procedimientos.sql` |
| La tasa no validaba 0 a 100 | Además del procedimiento, la tabla tiene `CHECK (tasa_interes BETWEEN 0 AND 100)`. | `db/01_tablas.sql` |
| Al restaurar, la recarga programaba el cierre del programa | La recarga ya no avisa el cierre y la espera de seguridad subió de 10 a 30 s. | `frontend/api.js`, `frontend/crud.js`, `backend/main.py` |
| El .exe sin información de versión | Se incorporan versión, empresa, descripción y derechos. La firma digital requiere un certificado de pago y no se incluye. | `recursos/version.txt`, `construir_exe.bat` |
| Bases ya creadas | Se migran solas (CVV y tasa). | `db/migracion/cvv_y_tasa.sql` |

## Datos del cliente en la apertura
| Observación | Qué se hizo | Dónde |
|---|---|---|
| `calle` del cliente permitía NULL y no se guardaba | `cliente.calle` es `NOT NULL` (y no puede ser solo espacios). El formulario la pide y `sp_abrir_cuenta`, `sp_cliente_crear` y `sp_cliente_editar` la guardan. | `db/01_tablas.sql`, `db/04_procedimientos.sql`, `frontend/index.html` |
| Se usaba la provincia de la agencia como provincia del cliente | El paso 1 pide departamento y provincia de residencia del cliente; el paso 3 sigue eligiendo la agencia con su propio departamento/provincia. La API envía la provincia del cliente en `provincia` y la agencia en `agencia`. | `frontend/index.html`, `frontend/api.js`, `backend/main.py` |
| Fecha de emisión del DNI y nacionalidad/residencia no se guardaban | Columnas `fecha_emision_dni` (no futura y no anterior al nacimiento) y `peruano_residente` (`CHECK` verdadero) en `cliente`. Los procedimientos validan y rechazan datos faltantes. | `db/01_tablas.sql`, `db/04_procedimientos.sql`, `backend/main.py` |
| Bases ya creadas | Se migran solas al abrir la aplicación. Los clientes anteriores reciben calle `Sin registrar`, una emisión estimada (a los 18 años) y la confirmación en verdadero: conviene corregirlos desde Clientes. | `db/migracion/direccion_y_dni.sql`, `backend/motor_bd.py` |

Los datos de ejemplo (`03_datos.sql`) y `scripts/probar_bd.py` se actualizaron; `docs/script_completo.sql` se regeneró con los cambios.

## Alineación con el modelo físico de la Cuarta Entrega
| Observación | Qué se hizo | Dónde |
|---|---|---|
| El nombre del cliente estaba en una sola columna (`nombres_completos`), lo que rompía la atomicidad (1FN) diseñada en la Cuarta Entrega | `cliente` guarda `nombres`, `apellido_paterno` y `apellido_materno` (VARCHAR(50), `NOT NULL`, sin textos en blanco). `sp_abrir_cuenta`, `sp_cliente_crear` y `sp_cliente_editar` reciben las tres partes y las validan con `fn_validar_nombre_cliente`. Las vistas exponen además `nombre_completo` (`concat_ws`) y los reportes lo arman igual, por lo que su salida no cambia. | `db/01_tablas.sql`, `db/04_procedimientos.sql`, `db/06_vistas.sql`, `db/07_reportes.sql` |
| El formulario pedía un solo campo de nombre | La validación con RENIEC (simulada) devuelve nombres, apellido paterno y apellido materno; el CRUD de clientes edita las tres partes y la API las envía por separado. | `frontend/index.html`, `frontend/api.js`, `frontend/crud.js`, `backend/main.py` |
| La calle de cliente y agencia admitía 80 caracteres y la Cuarta Entrega permite 100 | `cliente.calle` y `agencia.calle` pasan a `VARCHAR(100)`; el formulario acepta hasta 100. | `db/01_tablas.sql`, `frontend/index.html` |
| Bases ya creadas | Se migran solas al abrir la aplicación: las dos últimas palabras de `nombres_completos` pasan a apellido paterno y materno, el resto a nombres (si falta alguna parte queda `Sin registrar`). Los apellidos compuestos, como «De la Torre», pueden quedar mal repartidos: conviene revisarlos desde Clientes. | `db/migracion/nombres_y_calle.sql`, `backend/motor_bd.py` |

`03_datos.sql`, `scripts/probar_bd.py` (con pruebas nuevas de apellidos obligatorios y de calle de 100/101 caracteres) y `docs/script_completo.sql` se actualizaron.
