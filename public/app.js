/* public/app.js
   Cliente de auth (registro/login/sesión) con soporte local y GitHub Pages.
   - Endpoints: /auth/register, /auth/login, /auth/me
   - JWT en Authorization Bearer
*/

const $ = (sel) => document.querySelector(sel);
function getVal(...ids){ for (const id of ids){ const el=document.getElementById(id); if(el) return (el.value||"").trim(); } return ""; }
function setMsg(id, text, ok=false){ const el=document.getElementById(id); if(!el) return; el.textContent=text||""; el.style.color= ok ? "#16a34a" : "#c02626"; }
function clearMsg(id){ setMsg(id, ""); }

/* =================== API BASE (local vs GitHub Pages) =================== */
// Pon aquí el dominio de tu backend cuando lo despliegues (Render / Railway)
const RENDER_URL = "https://TU-APP.onrender.com"; // <- CAMBIA ESTO al publicar
// Permite override rápido guardando una base en localStorage.API_BASE
const API_BASE = (() => {
  const override = localStorage.getItem("API_BASE");
  if (override) return override.replace(/\/+$/, "");
  const h = location.hostname;
  // Si está en GitHub Pages, usa el backend público; en local usa mismo origen
  return h.endsWith("github.io") ? RENDER_URL.replace(/\/+$/, "") : "";
})();

/* =================== Auth storage =================== */
const AUTH_KEY = "scas_auth_token";
const USER_KEY = "scas_user_info";

function saveAuth(token, user){
  if (token) localStorage.setItem(AUTH_KEY, token);
  if (user)  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
function getToken(){ return localStorage.getItem(AUTH_KEY) || ""; }
function getUser(){ try { return JSON.parse(localStorage.getItem(USER_KEY)||"{}"); } catch { return {}; } }
function clearAuth(){
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_KEY);
  // llaves antiguas, por si quedaron de pruebas
  localStorage.removeItem("token");
  localStorage.removeItem("fullname");
}

/* =================== Fetch helper =================== */
async function api(path, { method="GET", body, auth=true, headers={} } = {}){
  // Prefija con API_BASE si la ruta no es absoluta
  const url = /^https?:\/\//i.test(path) ? path : `${API_BASE}${path}`;
  const opts = { method, headers: { ...headers } };

  if (body && !(body instanceof FormData)){
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  } else if (body instanceof FormData){
    opts.body = body;
  }

  if (auth){
    const t = getToken();
    if (t) opts.headers["Authorization"] = `Bearer ${t}`;
  }

  let res, data;
  try{
    res  = await fetch(url, opts);
  }catch(e){
    throw new Error("No se pudo conectar con el servidor.");
  }

  try{ data = await res.json(); }catch{ data = {}; }

  if (res.status === 401){
    clearAuth();
    if (!location.pathname.endsWith("/index.html")) {
      // vuelve al login si estabas en página protegida
      location.replace("index.html");
    }
    throw new Error(data?.error || "Sesión expirada.");
  }

  if (!res.ok || data?.ok === false){
    const msg = data?.error || `Error HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

/* =================== Registro =================== */
async function register(){
  const msgId = "regMsg";
  clearMsg(msgId);

  const fullname = getVal("regFullname","fullname");
  const email    = getVal("regEmail","email");
  const password = getVal("regPass","password");
  const gender   = getVal("regGender","gender"); // "M"|"F" opcional
  const age      = getVal("regAge","age");

  if (!fullname || !email || !password || !age){
    setMsg(msgId, "Completa todos los campos obligatorios.");
    return;
  }
  try{
    const out = await api("/auth/register", {
      method: "POST",
      auth: false,
      body: { fullname, email, password, gender, age }
    });
    saveAuth(out.token, { id: out.id, email: out.email, fullname: out.fullname, role: out.role });
    setMsg(msgId, "Registro exitoso. Redirigiendo…", true);
    setTimeout(() => location.replace("index.html"), 400);
  }catch(err){
    setMsg(msgId, err.message);
  }
}

/* =================== Login =================== */
async function login(){
  const msgId = "loginMsg";
  clearMsg(msgId);

  const email = getVal("loginEmail","email");
  const password = getVal("loginPass","password");
  if (!email || !password){
    setMsg(msgId, "Faltan credenciales.");
    return;
  }
  try{
    const out = await api("/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password }
    });
    saveAuth(out.token, { id: out.id, email: out.email, fullname: out.fullname, role: out.role });
    setMsg(msgId, "Ingreso correcto. Redirigiendo…", true);
    setTimeout(() => redirectByRole(out.role), 300);
  }catch(err){
    setMsg(msgId, err.message);
  }
}

/* =================== Sesión =================== */
async function loadMe(){
  try{
    const me = await api("/auth/me", { method: "GET", auth: true });
    saveAuth(getToken(), { id: me.id, email: me.email, fullname: me.fullname, role: me.role });
    const el = document.getElementById("welcomeName");
    if (el) el.textContent = me.fullname || "";
    return me;
  }catch{
    clearAuth();
    return null;
  }
}
function logout(){
  clearAuth();
  location.replace("index.html");
}

/* =================== Protección de páginas =================== */
async function requireAuthPage(requiredRole){
  const me = await loadMe();
  if (!me){ location.replace("index.html"); return; }
  if (requiredRole && me.role !== requiredRole){
    location.replace("student.html");
  }
}

/* =================== Atajos de formulario =================== */
function wireForms(){
  const logoutBtn = document.getElementById("btnLogout");
  if (logoutBtn) logoutBtn.addEventListener("click", (e)=>{ e.preventDefault(); logout(); });

  const regBtn = document.getElementById("registerBtn");
  if (regBtn) regBtn.addEventListener("click", (e)=>{ e.preventDefault(); register(); });

  const loginForm = document.getElementById("loginForm");
  if (loginForm) loginForm.addEventListener("submit", (e)=>{ e.preventDefault(); login(); });

  const registerForm = document.getElementById("registerForm");
  if (registerForm) registerForm.addEventListener("submit", (e)=>{ e.preventDefault(); register(); });

  ["loginEmail","loginPass"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("keydown", (e)=>{ if (e.key === "Enter"){ e.preventDefault(); login(); }});
  });
}

/* =================== Inicial por página =================== */
document.addEventListener("DOMContentLoaded", async () => {
  const page = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  wireForms();

  if (page === "" || page === "index.html"){ await loadMe(); }
  if (page === "student.html" || page === "results.html"){ await requireAuthPage(); }
  if (page === "admin.html"){ await requireAuthPage("admin"); }
});

/* =================== Utils =================== */
function redirectByRole(role){ location.replace(role === "admin" ? "admin.html" : "student.html"); }

/* Exponer en global si usas onclick=... */
window.login = login;
window.register = register;
window.logout = logout;
