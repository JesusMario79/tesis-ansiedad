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
  localStorage.removeItem(AUTH_KEY);  // "scas_auth_token"
  localStorage.removeItem(USER_KEY);  // "scas_user_info"
  // claves antiguas, por si quedaron de pruebas:
  localStorage.removeItem("token");
  localStorage.removeItem("fullname");
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
  try { data = await res.json(); } catch { /* puede no haber JSON */ }

  if (!res.ok || data?.ok === false) {
    const msg = data?.error || `Error HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

/* =============== Registro =============== */
async function register() {
  const msgId = "regMsg";
  clearMsg(msgId);

  const fullname = getVal("regFullname", "fullname");
  const email    = getVal("regEmail", "email");
  const password = getVal("regPass", "password");
  const gender   = getVal("regGender", "gender"); // "M" o "F"
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

    // Guarda token y usuario básico
    saveAuth(out.token, { id: out.id, email: out.email, fullname: out.fullname, role: out.role });
    setMsg(msgId, "Registro exitoso. Redirigiendo…", true);

    // Después de registrar, llévalo al login (index)
    setTimeout(() => location.replace("index.html"), 400);
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
    setTimeout(() => redirectByRole(out.role), 300);
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
  location.replace("index.html"); // evita volver con el botón “Atrás”
}

/* =============== Protección de páginas =============== */
async function requireAuthPage(requiredRole) {
  const me = await loadMe();
  if (!me) {
    location.replace("index.html");
    return;
  }
  if (requiredRole && me.role !== requiredRole) {
    // si no es admin e intenta entrar a admin.html, mándalo a student
    location.replace("student.html");
  }
}

/* =============== Atajos de formulario =============== */
function wireForms() {
  // Botón cerrar sesión (admin.html / student.html)
  const logoutBtn = document.getElementById("btnLogout");
  if (logoutBtn) logoutBtn.addEventListener("click", (e) => { e.preventDefault(); logout(); });

  // Botón registrar (si existe)
  const regBtn = document.getElementById("registerBtn");
  if (regBtn) regBtn.addEventListener("click", (e) => { e.preventDefault(); register(); });

  // Formularios <form> si existen
  const loginForm = document.getElementById("loginForm");
  if (loginForm) loginForm.addEventListener("submit", (e) => { e.preventDefault(); login(); });

  const registerForm = document.getElementById("registerForm");
  if (registerForm) registerForm.addEventListener("submit", (e) => { e.preventDefault(); register(); });

  // Enviar con Enter en login
  ["loginEmail", "loginPass"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); login(); } });
  });
}

/* =============== Inicialización por página =============== */
document.addEventListener("DOMContentLoaded", async () => {
  // Detecta por nombre de archivo
  const page = (location.pathname.split("/").pop() || "index.html").toLowerCase();

  wireForms();

  if (page === "" || page === "index.html") {
    // Solo valida sesión para mostrar saludo si corresponde
    await loadMe();
  }

  if (page === "student.html" || page === "results.html") {
    await requireAuthPage(); // cualquier usuario logueado
  }

  if (page === "admin.html") {
    await requireAuthPage("admin"); // solo admin
  }
});

/* =============== Utilidades varias =============== */
function redirectByRole(role) {
  location.replace(role === "admin" ? "admin.html" : "student.html");
}

/* =============== Exporta en global si usas onclick= ======= */
window.login = login;
window.register = register;
window.logout = logout;
