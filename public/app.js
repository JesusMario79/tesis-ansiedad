/* public/app.js
   Cliente simple para registro, login y sesión con JWT.
   - Endpoints: /auth/register, /auth/login, /auth/me
   - Guarda token en localStorage
   - Helpers para proteger páginas (student.html, admin.html, etc.)
*/

/* =============== Utils DOM =============== */
const $ = (sel) => document.querySelector(sel);

function getVal(...ids) {
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) return (el.value || "").trim();
  }
  return "";
}

function setMsg(targetId, text, ok = false) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.textContent = text || "";
  el.style.color = ok ? "#16a34a" : "#c02626";
}

function clearMsg(targetId) {
  setMsg(targetId, "");
}

/* =============== Auth storage =============== */
const AUTH_KEY = "scas_auth_token";
const USER_KEY = "scas_user_info";

function saveAuth(token, user) {
  if (token) localStorage.setItem(AUTH_KEY, token);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function getToken() {
  return localStorage.getItem(AUTH_KEY) || "";
}

function getUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || "{}"); }
  catch { return {}; }
}

function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_KEY);
}

/* =============== Fetch helper =============== */
async function api(path, { method = "GET", body, auth = true, headers = {} } = {}) {
  const opts = { method, headers: { ...headers } };

  if (body && !(body instanceof FormData)) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    opts.body = body;
  }

  if (auth) {
    const t = getToken();
    if (t) opts.headers["Authorization"] = `Bearer ${t}`;
  }

  const res = await fetch(path, opts);
  let data = {};
  try { data = await res.json(); } catch { /* texto vacío */ }

  if (!res.ok || data?.ok === false) {
    const msg = data?.error || `Error HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

/* =============== Registro =============== */
async function register() {
  const msgId = "registerMsg";
  clearMsg(msgId);

  const fullname = getVal("regFullname", "fullname");
  const email    = getVal("regEmail", "email");
  const password = getVal("regPass", "password");
  const gender   = getVal("regGender", "gender");   // "M" o "F" (opcional)
  const age      = getVal("regAge", "age");

  if (!fullname || !email || !password || !age) {
    setMsg(msgId, "Completa todos los campos obligatorios.");
    return;
  }

  try {
    const out = await api("/auth/register", {
      method: "POST",
      auth: false,
      body: { fullname, email, password, gender, age }
    });
    // guarda token y user básico
    saveAuth(out.token, { id: out.id, email: out.email, fullname: out.fullname, role: out.role });
    setMsg(msgId, "Registro exitoso. Redirigiendo…", true);
    // ve a la pantalla del estudiante
    setTimeout(() => location.href = "student.html", 400);
  } catch (err) {
    setMsg(msgId, err.message);
  }
}

/* =============== Login =============== */
async function login() {
  const msgId = "loginMsg";
  clearMsg(msgId);

  const email = getVal("loginEmail", "email");
  const password = getVal("loginPass", "password");
  if (!email || !password) {
    setMsg(msgId, "Faltan credenciales.");
    return;
  }

  try {
    const out = await api("/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password }
    });
    saveAuth(out.token, { id: out.id, email: out.email, fullname: out.fullname, role: out.role });
    setMsg(msgId, "Ingreso correcto. Redirigiendo…", true);
    setTimeout(() => location.href = "student.html", 300);
  } catch (err) {
    setMsg(msgId, err.message);
  }
}

/* =============== Sesión =============== */
async function loadMe() {
  // Verifica token contra /auth/me y actualiza saludo si existe #welcomeName
  try {
    const me = await api("/auth/me", { method: "GET", auth: true });
    saveAuth(getToken(), { id: me.id, email: me.email, fullname: me.fullname, role: me.role });
    const el = document.getElementById("welcomeName");
    if (el) el.textContent = me.fullname || "";
    return me;
  } catch {
    // token no válido
    clearAuth();
    return null;
  }
}

function logout() {
  clearAuth();
  location.href = "index.html";
}

/* =============== Protección de páginas =============== */
async function requireAuthPage() {
  const me = await loadMe();
  if (!me) location.href = "index.html";
}

/* =============== Atajos de formulario =============== */
function wireForms() {
  // Si existe un botón con id, conecta handlers
  const loginBtn = document.getElementById("loginBtn");
  if (loginBtn) loginBtn.addEventListener("click", (e) => { e.preventDefault(); login(); });

  const regBtn = document.getElementById("registerBtn");
  if (regBtn) regBtn.addEventListener("click", (e) => { e.preventDefault(); register(); });

  // Si hay formularios <form>, intercepta submit
  const loginForm = document.getElementById("loginForm");
  if (loginForm) loginForm.addEventListener("submit", (e) => { e.preventDefault(); login(); });

  const registerForm = document.getElementById("registerForm");
  if (registerForm) registerForm.addEventListener("submit", (e) => { e.preventDefault(); register(); });

  // Enviar con Enter si usas inputs sueltos
  ["loginEmail","loginPass"].forEach(id=>{
    const el = document.getElementById(id);
    if (el) el.addEventListener("keydown", (e)=>{ if (e.key === "Enter"){ e.preventDefault(); login(); }});
  });
}

/* =============== Inicialización por página =============== */
document.addEventListener("DOMContentLoaded", async () => {
  wireForms();

  // Detecta por nombre de archivo
  const page = (location.pathname.split("/").pop() || "index.html").toLowerCase();

  if (page === "" || page === "index.html") {
    // Si ya hay sesión válida, puedes redirigir al estudiante:
    // const me = await loadMe(); if (me) location.href = "student.html";
    await loadMe(); // o solo cargar saludo si existe
  }

  if (page === "student.html" || page === "results.html" || page === "admin.html") {
    await requireAuthPage();
  }
});

/* =============== Exporta en global si usas onclick= ======= */
window.login = login;
window.register = register;
window.logout = logout;
