// Inicio de sesión: pantalla de acceso, sesión y cierre de sesión
let TOKEN = null, USER = null;
try { const s = JSON.parse(sessionStorage.getItem("sesion")); if (s && s.token) { TOKEN = s.token; USER = s; } } catch (e) {}
const AUTH_API = location.protocol === "file:" ? "http://localhost:8000/api" : "/api";
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const loginEl = document.createElement("div");
loginEl.id = "login";
loginEl.innerHTML = `
 <section class="lg-brand"><div class="lg-logo">SC</div><h1>SAPCUBA</h1><p>Sistema de Apertura de Cuentas</p>
  <ul><li>Apertura de cuentas en pocos minutos</li><li>Información del cliente centralizada y segura</li><li>Acceso por roles con las cuentas de PostgreSQL</li></ul></section>
 <section class="lg-form"><form id="lf"><h2>Iniciar sesión</h2><p class="hint">Acceso exclusivo para personal autorizado.</p>
  <label for="lu">Usuario</label><input id="lu" name="username" autocomplete="username" required>
  <label for="lp">Contraseña</label><div class="pw"><input id="lp" name="password" type="password" autocomplete="current-password" required><button type="button" class="s" id="lv">Mostrar</button></div>
  <div class="err" id="le" role="alert"></div>
  <button class="p lg-btn" id="lb" type="submit">Ingresar</button>
  <p class="hint lg-demo">Usa tu usuario y contraseña de PostgreSQL. De prueba: <b>admin</b> / Admin123 · <b>agente</b> / Agente123</p></form></section>`;
document.body.appendChild(loginEl);
const $l = s => loginEl.querySelector(s);

$l("#lv").onclick = () => { const p = $l("#lp"), v = p.type == "password"; p.type = v ? "text" : "password"; $l("#lv").textContent = v ? "Ocultar" : "Mostrar"; };
$l("#lf").onsubmit = async e => {
  e.preventDefault();
  const b = $l("#lb"); b.disabled = true; b.textContent = "Ingresando…"; $l("#le").textContent = "";
  try {
    const r = await fetch(AUTH_API + "/login", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario: $l("#lu").value, clave: $l("#lp").value }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "No se pudo iniciar sesión");
    TOKEN = d.token; USER = d;
    try { sessionStorage.setItem("sesion", JSON.stringify(d)); } catch (x) {}
    $l("#lp").value = ""; S.view = "home"; await tot(); draw();
  } catch (x) { $l("#le").textContent = x.message == "Failed to fetch" ? "No hay conexión con el servidor." : x.message; }
  b.disabled = false; b.textContent = "Ingresar";
};
function salir(msg) {
  if (TOKEN && !msg) fetch(AUTH_API + "/logout", { method: "POST", headers: { Authorization: "Bearer " + TOKEN } }).catch(() => {});  // el servidor olvida la sesión
  TOKEN = USER = null; try { sessionStorage.removeItem("sesion"); } catch (e) {}
  S.view = "home"; draw(); if (msg) $l("#le").textContent = msg;
}
A.salir = () => salir();

const draw0 = draw;
window.draw = () => {
  document.querySelector("header").hidden = document.querySelector("main").hidden = !TOKEN;
  loginEl.style.display = TOKEN ? "none" : "flex";
  if (!TOKEN) { $l("#lu").focus(); return; }
  draw0();
  $("#usr").innerHTML = `<div class="who"><b>${esc(USER.nombre)}</b><small>${USER.rol == "ADMIN" ? "Administrador" : "Agente de agencia"}</small></div><button class="s out" data-act="salir">Cerrar sesión</button>`;
};
draw();
