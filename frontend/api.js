// Conecta los botones del prototipo con la API (sobrescribe las acciones locales de index.html)
const API = location.protocol === "file:" ? "http://localhost:8000/api" : "/api";
const j = async (u, o) => {
  const r = await fetch(API + u, { headers: { "Content-Type": "application/json", Authorization: "Bearer " + TOKEN }, ...o });
  const d = await r.json().catch(() => ({}));
  if (r.status === 401) { salir("Tu sesión expiró. Ingresa nuevamente."); throw new Error("Sesión expirada"); }
  if (!r.ok) throw new Error(d.detail || "Error del servidor");
  return d;
};
const post = (u, b) => j(u, { method: "POST", body: JSON.stringify(b || {}) });
const tot = async () => {
  try {
    const d = await j("/catalogos");
    db.ag = d.agencias;
    S.tot = d.totales;
    if (d.departamentos) CAT.dep = d.departamentos;
    if (d.provincias) CAT.prov = d.provincias;
    if (d.monedas) CAT.mon = d.monedas;
    if (d.ocupaciones) CAT.ocu = d.ocupaciones;
  } catch (e) { toast("No hay conexión con la API"); }
};
const cargar = async dni => { const d = await j("/clientes/" + dni); db.cli = [d.cliente]; db.cta = d.cuentas; db.tar = d.tarjetas; };
const refresh = async () => { await cargar(S.found); draw(); };
const run = (fn, ok) => async el => { try { await fn(el); if (ok) toast(ok); } catch (e) { toast(e.message); } };

const go0 = A.go;
A.go = async el => { await tot(); go0(el); };
A.confirm = run(async () => {
  const f = S.f;
  S.res = await post("/aperturas", { dni: f.dni, nombres: f.nomb, apellido_paterno: f.ap, apellido_materno: f.am, nacimiento: f.fnac, correo: f.mail, telefono: f.tel,
    ocupacion: f.ocu, provincia: +f.cprov, calle: f.calle.trim(), emision_dni: f.emi, peruano_residente: f.nac,
    moneda: f.mon, agencia: +f.ag, tarjeta: f.tar });  // provincia = la del CLIENTE; agencia = la agencia elegida
  S.view = "done"; draw();
}, "Apertura guardada en PostgreSQL");
A.verc = run(async () => { S.q = S.res.dni; await cargar(S.q); S.found = S.q; S.view = "acc"; draw(); });
A.buscar = async () => { const q = $("#q").value.trim(); S.q = q; try { await cargar(q); S.found = q; } catch (e) { S.found = false; } draw(); };
A.addtel = run(async () => { await post(`/clientes/${S.found}/telefonos`, { telefono: $("#nt").value.trim() }); await refresh(); }, "Teléfono agregado");
A.tglcta = run(async el => { await post(`/cuentas/${el.dataset.id}/estado`); await refresh(); }, "Estado de cuenta actualizado");
A.emitir = run(async el => { await post(`/cuentas/${el.dataset.id}/tarjeta`); await refresh(); }, "Tarjeta emitida");
A.perdida = run(async el => {
  if (!confirm("¿Marcar esta tarjeta como perdida y emitir una réplica?")) return;
  await post(`/tarjetas/${el.dataset.id}/reemplazo`); await refresh();
}, "Tarjeta inactivada y réplica emitida");
A.report = run(async el => { S.rep = el.dataset.k; S.repD = await j("/reportes/" + S.rep); draw(); });
A.tglag = run(async el => { await post(`/agencias/${el.dataset.id}/estado`); await tot(); draw(); }, "Agencia actualizada");

window.repTable = () => {
  const d = S.repD; if (!d) return "";
  const rows = d.rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("");
  return `<table><tr>${d.H.map(x => `<th>${x}</th>`).join("")}</tr>${rows || `<tr><td class="hint" colspan="${d.H.length}">Sin resultados.</td></tr>`}</table>`;
};

db.cli = []; db.cta = []; db.tar = [];
if (TOKEN) tot().then(draw);

// Latido: avisa al programa que la ventana sigue abierta; al cerrarla, SAPCUBA guarda un respaldo y se apaga solo
const latido = () => fetch(API + "/latido", { method: "POST" }).catch(() => {});
latido(); setInterval(latido, 5000);
let RECARGANDO = false;  // al restaurar un respaldo la página se recarga a propósito: no debe pedir el cierre del programa
addEventListener("pagehide", () => { if (RECARGANDO) return; try { navigator.sendBeacon(API + "/cerrar"); } catch (e) {} });
