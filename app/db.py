# app/db.py
import os
from sqlalchemy import create_engine, text
from passlib.hash import bcrypt  # <-- en vez de werkzeug

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("DB_PASS", ""))  # <-- acepta ambos
DB_NAME = os.getenv("DB_NAME", "tesis_ansiedad")

SERVER_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"
DATABASE_URL = f"{SERVER_URL}/{DB_NAME}?charset=utf8mb4"

_server_engine = None
_engine = None

def server_engine():
    global _server_engine
    if _server_engine is None:
        _server_engine = create_engine(SERVER_URL, future=True, pool_pre_ping=True)
    return _server_engine

def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
    return _engine

def create_database_if_needed():
    # usamos .begin() para asegurarnos de que se aplique
    with server_engine().begin() as conn:
        conn.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))

def _add_col_if_missing(conn, table, col, ddl):
    present = conn.execute(text("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=:db AND TABLE_NAME=:tbl AND COLUMN_NAME=:col
    """), {"db": DB_NAME, "tbl": table, "col": col}).scalar()
    if not present:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))

def create_tables_if_needed():
    with engine().begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fullname VARCHAR(150) NOT NULL,
            email VARCHAR(190) NOT NULL UNIQUE,
            role ENUM('admin','student') NOT NULL DEFAULT 'student',
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))
        # asegurar columnas nuevas sin usar IF NOT EXISTS
        _add_col_if_missing(conn, "users", "gender", "gender ENUM('M','F') NULL AFTER password_hash")
        _add_col_if_missing(conn, "users", "age",    "age TINYINT UNSIGNED NULL AFTER gender")


def ensure_admin():
    admin_email = (os.getenv("ADMIN_EMAIL", "admin@local") or "").lower()
    admin_pass  = os.getenv("ADMIN_PASSWORD", os.getenv("ADMIN_PASS", "admin123"))
    admin_name  = os.getenv("ADMIN_NAME", "Administrador")
    with engine().begin() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE email=:e"), {"e": admin_email}).first()
        if not row:
            conn.execute(text("""
                INSERT INTO users (fullname, email, role, password_hash)
                VALUES (:n, :e, 'admin', :ph)
            """), {
                "n": admin_name,
                "e": admin_email,
                "ph": bcrypt.hash(admin_pass)  # <-- ahora sí bcrypt
            })

def db_one(q, params=None):
    with engine().connect() as conn:
        row = conn.execute(text(q), params or {}).mappings().first()
        return dict(row) if row else None

def db_all(q, params=None):
    with engine().connect() as conn:
        rows = conn.execute(text(q), params or {}).mappings().all()
        return [dict(r) for r in rows]

def db_exec(q, params=None):
    with engine().begin() as conn:
        res = conn.execute(text(q), params or {})
        return res.rowcount   # <- devuelve cuántas filas se afectaron

