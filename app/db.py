# app/db.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()  # carga variables desde .env

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or not DATABASE_URL.startswith("mysql+pymysql://"):
    raise RuntimeError("Configura DATABASE_URL con MySQL (mysql+pymysql://user:pass@host:port/db)")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,   # evita timeouts en cloud
    poolclass=QueuePool,
    future=True,
)

def db_one(sql: str, params: dict | None = None):
    """Devuelve un solo registro como dict o None."""
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None

def db_all(sql: str, params: dict | None = None):
    """Devuelve lista de dicts."""
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]

def db_exec(sql: str, params: dict | None = None) -> int:
    """Ejecuta INSERT/UPDATE/DELETE. Retorna filas afectadas."""
    with engine.begin() as conn:
        res = conn.execute(text(sql), params or {})
        return res.rowcount
