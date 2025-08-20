# app/db.py
import os
from sqlalchemy import create_engine, text
from urllib.parse import urlparse, unquote
from passlib.hash import bcrypt  # para hashear contraseñas

# ----------------------------
# Config desde variables .env
# ----------------------------
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("DB_PASS", ""))  # acepta DB_PASSWORD o DB_PASS
DB_NAME = os.getenv("DB_NAME", "tesis_ansiedad")

SERVER_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"
DATABASE_URL = f"{SERVER_URL}/{DB_NAME}?charset=utf8mb4"

# Engines (perezosos)
_server_engine = None
_engine = None


def server_engine():
    """Engine sin DB seleccionada (para CREATE DATABASE, etc.)."""
    global _server_engine
    if _server_engine is None:
        _server_engine = create_engine(
            SERVER_URL, future=True, pool_pre_ping=True
        )
    return _server_engine


def engine():
    """Engine de la base de datos de la app."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL, future=True, pool_pre_ping=True
        )
    return _engine


# ----------------------------
# Bootstrap de base de datos
# ----------------------------
def create_database_if_needed():
    """Crea la base si no existe (utf8mb4)."""
    with server_engine().begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )


def _add_col_if_missing(conn, table, col, ddl):
    """Agrega columna si no existe (útil para evoluciones)."""
    present = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA=:db AND TABLE_NAME=:tbl AND COLUMN_NAME=:col
            """
        ),
        {"db": DB_NAME, "tbl": table, "col": col},
    ).scalar()
    if not present:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def create_tables_if_needed():
    """Crea todas las tablas requeridas si no existen."""
    with engine().begin() as conn:
        # Usuarios
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fullname VARCHAR(150) NOT NULL,
                    email VARCHAR(190) NOT NULL UNIQUE,
                    role ENUM('admin','student') NOT NULL DEFAULT 'student',
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        )
        # Evoluciones opcionales
        _add_col_if_missing(conn, "users", "gender", "gender ENUM('M','F') NULL AFTER password_hash")
        _add_col_if_missing(conn, "users", "age", "age TINYINT UNSIGNED NULL AFTER gender")
        _add_col_if_missing(conn, "surveys", "description", "description VARCHAR(255) NULL AFTER title")
        _add_col_if_missing(conn, "surveys", "min_age",    "min_age TINYINT UNSIGNED NOT NULL AFTER description")
        _add_col_if_missing(conn, "surveys", "max_age",    "max_age TINYINT UNSIGNED NOT NULL AFTER min_age")


        # Encuestas
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS surveys (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(64) NOT NULL UNIQUE,
                    title VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        )

        # Ítems de encuesta
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS survey_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    survey_id INT NOT NULL,
                    item_number INT NOT NULL,
                    prompt VARCHAR(512) NOT NULL,
                    is_scored TINYINT(1) NOT NULL DEFAULT 1,
                    subscale ENUM('GAD','SOC','OCD','PAA','PHB','SAD') NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_si_survey
                        FOREIGN KEY (survey_id) REFERENCES surveys(id)
                        ON DELETE CASCADE,
                    UNIQUE KEY uq_survey_item (survey_id, item_number),
                    INDEX ix_si_survey (survey_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        )

        # Respuestas (cabecera)
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS responses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    survey_id INT NOT NULL,
                    total_score INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_resp_user
                        FOREIGN KEY (user_id) REFERENCES users(id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_resp_survey
                        FOREIGN KEY (survey_id) REFERENCES surveys(id)
                        ON DELETE CASCADE,
                    INDEX ix_resp_user (user_id),
                    INDEX ix_resp_survey (survey_id),
                    INDEX ix_resp_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        )

        # Respuestas por ítem (detalle)
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS response_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    response_id INT NOT NULL,
                    item_id INT NOT NULL,
                    value TINYINT UNSIGNED NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_ri_resp
                        FOREIGN KEY (response_id) REFERENCES responses(id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_ri_item
                        FOREIGN KEY (item_id) REFERENCES survey_items(id)
                        ON DELETE CASCADE,
                    UNIQUE KEY uq_resp_item (response_id, item_id),
                    INDEX ix_ri_resp (response_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        )


def ensure_admin():
    """Crea un admin por defecto si no existe."""
    admin_email = (os.getenv("ADMIN_EMAIL", "admin@local") or "").lower()
    admin_pass = os.getenv("ADMIN_PASSWORD", os.getenv("ADMIN_PASS", "admin123"))
    admin_name = os.getenv("ADMIN_FULLNAME") or os.getenv("ADMIN_NAME", "Administrador")

    with engine().begin() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE email=:e"), {"e": admin_email}
        ).first()
        if not row:
            conn.execute(
                text(
                    """
                    INSERT INTO users (fullname, email, role, password_hash)
                    VALUES (:n, :e, 'admin', :ph)
                    """
                ),
                {"n": admin_name, "e": admin_email, "ph": bcrypt.hash(admin_pass)},
            )


# ----------------------------
# Helpers de acceso
# ----------------------------
def db_one(q, params=None):
    """Devuelve un dict (o None)."""
    with engine().connect() as conn:
        row = conn.execute(text(q), params or {}).mappings().first()
        return dict(row) if row else None


def db_all(q, params=None):
    """Devuelve lista de dicts."""
    with engine().connect() as conn:
        rows = conn.execute(text(q), params or {}).mappings().all()
        return [dict(r) for r in rows]


def db_exec(q, params=None):
    """Ejecuta DML (INSERT/UPDATE/DELETE) confirmando la transacción."""
    with engine().begin() as conn:
        res = conn.execute(text(q), params or {})
        return res.rowcount  # filas afectadas
