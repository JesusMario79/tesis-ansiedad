# app/auth.py
"""
Rutas de autenticación (registro, login, perfil).
Dependen de:
- db_one, db_exec (helpers en app.db)
- make_token, require_auth, EMAIL_ALLOWED, NAME_ALLOWED (en app.utils)
- passlib[bcrypt] para hashing seguro
"""

from flask import Blueprint, request, jsonify
from passlib.hash import bcrypt
from sqlalchemy.exc import IntegrityError

from .db import db_one, db_exec
from .utils import make_token, require_auth, EMAIL_ALLOWED, NAME_ALLOWED

# Prefijo /auth para que tus llamadas del front sean /auth/register y /auth/login
bp = Blueprint("auth", __name__, url_prefix="/auth")


# -------- utilidades internas --------
def _payload() -> dict:
    """Soporta JSON y x-www-form-urlencoded."""
    return request.get_json(silent=True) or request.form or {}


def _ok(**data):
    return jsonify({"ok": True, **data})


def _bad(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code


# -------- endpoints --------

@bp.post("/register")
def register():
    data = _payload()

    fullname = (data.get("fullname") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")
    gender   = (data.get("gender") or "").strip()  # "M" o "F" (opcional)
    age_raw  = (data.get("age") or "")

    # --- Validaciones ---
    if not fullname or not NAME_ALLOWED.match(fullname):
        return _bad("Nombre inválido: usa solo letras y espacios.")

    if not EMAIL_ALLOWED.match(email):
        return _bad("Correo inválido: debe iniciar con letra y terminar en @gmail.com o @hotmail.com.")

    try:
        age = int(str(age_raw).strip())
    except ValueError:
        return _bad("Edad inválida: usa solo números.")

    if age < 12 or age > 15:
        return _bad("Edad fuera de rango: solo de 12 a 15 años.")

    if len(password) < 6 or len(password) > 10:
        return _bad("La contraseña debe tener entre 6 y 10 caracteres.")

    if gender and gender not in ("M", "F"):
        return _bad("Género inválido (usa M o F).")

    role = "student"

    # Inserción con captura de UNIQUE(email)
    pwd_hash = bcrypt.hash(password)
    try:
        affected = db_exec(
            """
            INSERT INTO users (fullname, email, password_hash, role, gender, age)
            VALUES (:fn, :em, :ph, :ro, :ge, :ag)
            """,
            {"fn": fullname, "em": email, "ph": pwd_hash, "ro": role, "ge": (gender or None), "ag": age}
        )
        if not affected:
            return _bad("No se pudo registrar. Intenta nuevamente.", 500)
    except IntegrityError:
        return _bad("Ya existe un usuario registrado con este correo.")

    # Recupera id para incluirlo en el token/respuesta
    user = db_one("SELECT id FROM users WHERE email=:e", {"e": email})
    uid = user["id"] if user else None

    token = make_token({"id": uid, "email": email, "role": role, "fullname": fullname})
    return _ok(token=token, id=uid, role=role, fullname=fullname, email=email)


@bp.post("/login")
def login():
    data = _payload()
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")

    if not email or not password:
        return _bad("Faltan credenciales.")

    user = db_one("SELECT id, fullname, email, role, password_hash FROM users WHERE email=:e", {"e": email})
    if not user:
        return _bad("Usuario no encontrado.")
    if not bcrypt.verify(password, user["password_hash"]):
        return _bad("Contraseña incorrecta.")

    token = make_token({"id": user["id"], "email": user["email"], "role": user["role"], "fullname": user["fullname"]})
    return _ok(token=token, id=user["id"], role=user["role"], fullname=user["fullname"], email=user["email"])


@bp.get("/me")
@require_auth()
def me():
    u = request.user  # establecido por require_auth()
    return _ok(id=u.get("id"), email=u.get("email"), role=u.get("role"), fullname=u.get("fullname"))
