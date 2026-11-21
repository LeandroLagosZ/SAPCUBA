# Manual de usuario · SAPCUBA (Sistema de Apertura de Cuentas)

**Quién lo usa:** el trabajador de agencia. Se abre con doble clic en `SAPCUBA.exe` y funciona en su propia ventana. Para salir, cierra la ventana: el sistema guarda un respaldo y se apaga solo.

## 0. Inicio de sesión
Escribe tu usuario y contraseña de PostgreSQL (los de prueba son `admin` / `Admin123` y `agente` / `Agente123`) y pulsa **Ingresar**; el botón **Mostrar** deja ver la contraseña. Para salir usa **Cerrar sesión** (arriba a la derecha). La sesión vence a las 8 horas. El **Agente** no puede dar de baja ni activar registros ni gestionar agencias y respaldos; el **Administrador** puede todo. Si tu usuario existe pero no pertenece a ningún grupo de SAPCUBA, el sistema te lo indica: pide al administrador de la base que te agregue a `sapcuba_agente` o `sapcuba_admin`.

## 1. Menú superior
Inicio · Nueva apertura · Consultar cliente · Clientes · Agencias · Cuentas · Tarjetas · Reportes · Administración.

## 2. Abrir una cuenta (Nueva apertura)
1. **Datos personales:** escribe DNI (8 dígitos), fecha de emisión del DNI, teléfono (9 dígitos) y correo; elige el departamento y la provincia **donde vive el cliente** y escribe su calle y número; marca la casilla de nacionalidad peruana y residencia; pulsa **Validar DNI con RENIEC** y luego **Siguiente**. La calle, la provincia, la fecha de emisión y la confirmación de nacionalidad/residencia se guardan en el cliente.
2. **Moneda:** elige Soles o Dólares y pulsa **Siguiente**.
3. **Ocupación y agencia:** elige la ocupación y una agencia activa (el departamento y la provincia de este paso son los de la **agencia**, no los del cliente); pulsa **Siguiente**.
4. **Confirmación:** revisa los datos, marca o desmarca *Emitir tarjeta* y pulsa **Confirmar apertura**.
5. Verás el número de cuenta, el CCI, el contrato y la tarjeta. **Copiar datos**, **Ver cuentas del cliente** y **Abrir otra cuenta** completan el flujo.

## 3. Consultar cliente
Escribe el DNI y pulsa **Buscar**. Desde ahí: **Agregar teléfono**, **Abrir otra cuenta**, **Activar/Desactivar cuenta**, **Emitir tarjeta nueva** y **Reportar pérdida y emitir réplica** (la tarjeta queda inactiva y se crea otra).

## 4. Clientes, Agencias, Cuentas y Tarjetas (CRUD)
- **Nuevo registro** (clientes y agencias): llena el formulario y pulsa **Guardar**.
- **Editar:** cambia los campos permitidos y pulsa **Guardar**.
- **Dar de baja:** confirma el aviso. El registro no se borra: queda *Inactivo* y el administrador puede volver a activarlo con **Activar**. Si tiene datos relacionados activos (por ejemplo, un cliente con cuentas activas) el sistema lo impide y lo explica.
- Las cuentas nuevas se crean con **Abrir cuenta nueva** y las tarjetas con **Emitir tarjeta nueva**.

## 5. Reportes
Pulsa uno de los once: cuentas por cliente, por moneda y por agencia; clientes con varias cuentas; tarjetas inactivas; clientes por ocupación y por departamento; tarjetas por marca; tarjetas por vencer; mayores saldos por moneda y cuentas sin tarjeta activa.

## 6. Administración
**Respaldo y recuperación** (solo administrador): *Generar respaldo ahora* crea un archivo `.backup` en `Documentos\SAPCUBA\Respaldos`; además SAPCUBA hace uno automático cada vez que se cierra (conserva los últimos 10). Para volver a un respaldo, pulsa **Restaurar** en su fila y confirma: se reemplazan todos los datos actuales (antes se guarda una copia de seguridad de ellos).
**Probar conexión con PostgreSQL** y activar o desactivar agencias.

## 7. Mensajes frecuentes
| Mensaje | Qué hacer |
|---|---|
| Usuario o contraseña incorrectos | Son los de PostgreSQL; pide al administrador que verifique o restablezca tu clave (`ALTER ROLE`). |
| No tienes permiso para esta acción | Tu rol (agente) no puede hacerlo; pídelo a un administrador. |
| La agencia no está activa | Elige otra agencia o actívala en Administración. |
| No se puede emitir tarjeta: la cuenta está inactiva | Activa la cuenta primero. |
| Ya existe un registro con ese valor | DNI, correo o anexo repetido. |
| No hay conexión con la API | Cierra SAPCUBA y vuelve a abrirlo. Si persiste, revisa `AppData\Local\SAPCUBA\sapcuba.log`. |
