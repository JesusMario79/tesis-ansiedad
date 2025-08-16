# app/utils.py
import os
import re
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional, Callable, Any, Dict
from flask import request, jsonify
from dotenv import load_dotenv
from jwt import ExpiredSignatureError, InvalidTokenError

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "clave_secreta_super_segura")

# Validaciones
# Nombre: solo letras (mayúsc/minúsc) + espacios (incluye acentos)
NAME_ALLOWED  = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]+$")

# Email: debe empezar con letra y terminar en @gmail.com o @hotmail.com
EMAIL_ALLOWED = re.compile(
    r"^[A-Za-z][A-Za-z0-9._%+-]*@(gmail\.com|hotmail\.com)$",
    re.IGNORECASE
)

def make_token(payload: Dict[str, Any], hours: int = 2) -> str:
    now = datetime.now(timezone.utc)
    data = {**payload, "iat": now, "exp": now + timedelta(hours=hours)}
    return jwt.encode(data, JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "iat"]})

def require_auth(role: Optional[str] = None) -> Callable:
    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "No token"}), 401
            token = auth[7:]
            try:
                user = verify_token(token)
            except ExpiredSignatureError:
                return jsonify({"error": "Token expirado"}), 401
            except InvalidTokenError:
                return jsonify({"error": "Token inválido"}), 401

            if role and user.get("role") != role:
                return jsonify({"error": "No autorizado"}), 403

            request.user = user  # type: ignore[attr-defined]
            return fn(*args, **kwargs)
        return wrapper
    return deco

def level_from_score(total: Optional[int]) -> Optional[str]:
    if total is None: return None
    if total >= 76:   return "Grave"
    if total >= 38:   return "Moderado"
    return "Leve"
