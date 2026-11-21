// CRUD completo (Clientes, Agencias, Cuentas, Tarjetas), respaldos y prueba de conexión
const ENT = {
  clientes: { t: "Clientes", key: "dni", nuevo: 1, activar: 1, lock: ["dni"], extra: ["estado"],
    F: [["dni", "DNI"], ["nombres", "Nombres"], ["apellido_paterno", "Apellido paterno"], ["apellido_materno", "Apellido materno"], ["nacimiento", "Fecha de nacimiento", "date"], ["correo", "Correo"], ["ocupacion", "Ocupación"], ["provincia", "Cód. provincia", "number"], ["calle", "Calle"], ["emision_dni", "Emisión del DNI", "date"]] },
  agencias: { t: "Agencias", key: "cod", nuevo: 1, activar: 1, lock: ["cod"], extra: ["estado"],
    F: [["cod", "Código", "number"], ["nombre", "Nombre"], ["calle", "Calle"], ["provincia", "Cód. provincia", "number"], ["anexo", "Anexo"]] },
  cuentas: { t: "Cuentas", key: "numero", nuevo: 0, activar: 1, lock: ["numero"], extra: ["dni", "moneda", "saldo", "estado"],
    F: [["numero", "N.º de cuenta"], ["tasa", "Tasa de interés (%)", "number"]] },
  tarjetas: { t: "Tarjetas", key: "numero", nuevo: 0, lock: ["numero"], extra: ["cuenta", "vence", "estado"],
    F: [["numero", "N.º de tarjeta"], ["marca", "Marca"]] },
};
const loadE = async () => { S.rows = await j("/crud/" + S.ent); };

V.crud = () => {
  const E = ENT[S.ent], ed = S.ed, cols = E.F.map(f => f[0]).concat(E.extra);
  let h = `<h1>${E.t}</h1>`;
  if (ed) h += `<div class="card"><h2>${ed.nuevo ? "Nuevo registro" : "Editar registro"}</h2><div class="row">${E.F.map(([k, l, t]) =>
    `<div><label>${l}</label><input data-e="${k}" type="${t || "text"}" value="${ed.v[k] ?? ""}" ${!ed.nuevo && E.lock.includes(k) ? "disabled" : ""}></div>`).join("")}</div>
    <div class="bar"><button class="p" data-act="guardar">Guardar</button><button class="s" data-act="cancelar">Cancelar</button></div></div>`;
  const nuevo = E.nuevo ? `<button class="p" data-act="nuevoE">Nuevo registro</button>` : S.ent == "cuentas" ? `<button class="p" data-act="nueva">Abrir cuenta nueva</button>` : "";
  h += `<div class="card tw">${nuevo ? `<div class="bar" style="margin:0 0 10px">${nuevo}</div>` : ""}<table><tr>${cols.map(c => `<th>${c}</th>`).join("")}<th></th></tr>
  ${S.rows.map((r, i) => `<tr>${cols.map(c => `<td>${c == "estado" ? tag(r[c]) : r[c]}</td>`).join("")}<td><button class="s" data-act="editar" data-i="${i}">Editar</button> ${USER.rol != "ADMIN" ? "" : r.estado == 0 ? (E.activar ? `<button class="s" data-act="activar" data-i="${i}">Activar</button>` : "") : `<button class="d" data-act="eliminar" data-i="${i}">Dar de baja</button>`}</td></tr>`).join("") || `<tr><td class="hint" colspan="${cols.length + 1}">Sin registros.</td></tr>`}</table></div>`;
  return h;
};
const adm0 = V.adm;
const respaldoCard = () => {
  if (USER.rol != "ADMIN") return `<div class="card"><h2>Respaldo y recuperación</h2><p class="hint">Solo el administrador puede gestionar los respaldos.</p></div>`;
  const b = S.bk || { items: [] };
  if (b.error) return `<div class="card"><h2>Respaldo y recuperación</h2><p class="hint">${esc(b.error)}</p></div>`;
  return `<div class="card"><h2>Respaldo y recuperación</h2>
    <p class="hint">SAPCUBA guarda un respaldo automático cada vez que cierras el programa (se conservan los últimos 10). También puedes generar uno cuando quieras. Para pasar tus datos a otra computadora, copia un archivo .backup a su carpeta de respaldos y restáuralo allí.</p>
    <div class="bar" style="margin-top:0"><button class="p" data-act="bkNuevo">Generar respaldo ahora</button></div>
    <p class="hint">Carpeta de respaldos: <b>${esc(b.carpeta || "")}</b></p>
    ${b.items.length ? `<div class="tw"><table><tr><th>Fecha</th><th>Tipo</th><th>Tamaño</th><th>Archivo</th><th></th></tr>${b.items.map((x, i) =>
      `<tr><td>${esc(x.fecha)}</td><td>${esc(x.tipo)}</td><td>${x.kb} KB</td><td>${esc(x.nombre)}</td><td><button class="s" data-act="bkRestaurar" data-i="${i}">Restaurar</button></td></tr>`).join("")}</table></div>` : `<p class="hint">Aún no hay respaldos.</p>`}</div>`;
};
V.adm = () => adm0().replace("</h1>", "</h1>" + respaldoCard()) + `<div class="card"><h2>Prueba de conexión</h2><div class="bar" style="margin-top:0"><button class="p" data-act="ping">Probar conexión con PostgreSQL</button></div><p id="ping" class="hint"></p></div>`;

window.nav = () => {
  const t = [["home", "Inicio"], ["open", "Nueva apertura"], ["acc", "Consultar cliente"], ["crud:clientes", "Clientes"], ["crud:agencias", "Agencias"],
    ["crud:cuentas", "Cuentas"], ["crud:tarjetas", "Tarjetas"], ["rep", "Reportes"], ["adm", "Administración"]];
  $("#nav").innerHTML = t.map(([v, l]) => `<button data-act="go" data-v="${v}" class="${(S.view == "crud" ? v == "crud:" + S.ent : S.view == v) ? "on" : ""}">${l}</button>`).join("");
};
const go1 = A.go;
A.go = async el => {
  const v = el.dataset.v;
  try {
    if (v.startsWith("crud:")) { await tot(); S.ent = v.slice(5); S.ed = null; await loadE(); S.view = "crud"; draw(); }
    else if (v == "adm") {
      await tot();
      if (USER.rol == "ADMIN") { try { S.bk = await j("/respaldos"); } catch (e) { S.bk = { error: e.message }; } }
      S.view = "adm"; draw();
    }
    else if (v == "rep") { await tot(); if (!S.reps) S.reps = await j("/reportes"); S.rep = null; S.view = "rep"; draw(); }
    else go1(el);
  } catch (e) { toast(e.message); }
};
A.nuevoE = () => { S.ed = { nuevo: 1, v: {} }; draw(); };
A.editar = el => { S.ed = { nuevo: 0, v: { ...S.rows[el.dataset.i] } }; draw(); };
A.cancelar = () => { S.ed = null; draw(); };
A.guardar = run(async () => {
  const E = ENT[S.ent], v = { ...S.ed.v };
  E.F.forEach(([k, , t]) => { if (t == "number") v[k] = +v[k]; });
  if (S.ed.nuevo) await post("/crud/" + S.ent, v);
  else await j(`/crud/${S.ent}/${S.ed.v[E.key]}`, { method: "PUT", body: JSON.stringify(v) });
  S.ed = null; await loadE(); draw();
}, "Guardado");
A.eliminar = run(async el => {
  const E = ENT[S.ent], r = S.rows[el.dataset.i];
  if (!confirm("¿Dar de baja este registro? Quedará inactivo (no se borra) y se puede volver a activar.")) return;
  await j(`/crud/${S.ent}/${r[E.key]}`, { method: "DELETE" }); await loadE(); draw();
}, "Registro dado de baja");
A.activar = run(async el => {
  const E = ENT[S.ent], r = S.rows[el.dataset.i];
  await post(`/crud/${S.ent}/${r[E.key]}/activar`); await loadE(); draw();
}, "Registro activado");
A.ping = async () => {
  try { const d = await j("/salud"); $("#ping").textContent = `Conectado: ${d.version_bd} · ${d.tablas} tablas · ${d.vistas} vistas · ${d.triggers} triggers · ${d.procedimientos} procedimientos y funciones almacenados`; }
  catch (e) { $("#ping").textContent = "Sin conexión: " + e.message; }
};
document.addEventListener("input", e => { const k = e.target.dataset.e; if (k && S.ed) S.ed.v[k] = e.target.value; });
A.bkNuevo = run(async () => { await post("/respaldos"); S.bk = await j("/respaldos"); draw(); }, "Respaldo generado");
A.bkRestaurar = run(async el => {
  const x = S.bk.items[el.dataset.i];
  if (!confirm(`Se reemplazarán TODOS los datos actuales por los del respaldo del ${x.fecha}.\nAntes se guardará una copia de los datos actuales. ¿Continuar?`)) return;
  await post("/respaldos/restaurar", { nombre: x.nombre });
  toast("Datos restaurados. Recargando…"); RECARGANDO = true; setTimeout(() => location.reload(), 1200);
});
