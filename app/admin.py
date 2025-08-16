# app/admin.py
from __future__ import annotations

from flask import Blueprint, jsonify
from .db import db_all, db_one
from .utils import require_auth, level_from_score

bp = Blueprint("admin", __name__)

def _students_rows():
    # CTEs para último intento por alumno (last) y conteo de intentos (agg)
    sql = """
    WITH last AS (
      SELECT r.user_id, r.total_score, r.created_at
      FROM responses r
      JOIN surveys s ON s.id = r.survey_id AND s.code = 'SCAS_CHILD'
      JOIN (
        SELECT r2.user_id, MAX(r2.created_at) AS last_dt
        FROM responses r2
        JOIN surveys s2 ON s2.id = r2.survey_id AND s2.code = 'SCAS_CHILD'
        GROUP BY r2.user_id
      ) t ON t.user_id = r.user_id AND t.last_dt = r.created_at
    ),
    agg AS (
      SELECT r.user_id, COUNT(*) AS attempts
      FROM responses r
      JOIN surveys s ON s.id = r.survey_id AND s.code = 'SCAS_CHILD'
      GROUP BY r.user_id
    )
    SELECT
      u.fullname,
      u.email,
      IFNULL(a.attempts, 0)              AS attempts,
      l.total_score                      AS last_score,
      l.created_at                       AS last_date
    FROM users u
    LEFT JOIN agg a  ON a.user_id = u.id
    LEFT JOIN last l ON l.user_id = u.id
    WHERE u.role = 'student'
    ORDER BY COALESCE(l.created_at, '') DESC
    """
    rows = db_all(sql)
    # agrega etiqueta de nivel para el último puntaje
    out = []
    for r in rows:
        d = dict(r)
        d["last_level"] = level_from_score(d["last_score"]) if d["last_score"] is not None else None
        out.append(d)
    return out

def _stats():
    st = db_one("SELECT COUNT(*) AS c FROM users WHERE role='student'")
    at = db_one("""
      SELECT COUNT(*) AS c
      FROM responses r
      JOIN surveys s ON s.id = r.survey_id AND s.code='SCAS_CHILD'
    """)
    # promedio de último puntaje (sobre quienes tienen al menos un intento)
    avg = db_one("""
      WITH last AS (
        SELECT r.user_id, r.total_score
        FROM responses r
        JOIN surveys s ON s.id=r.survey_id AND s.code='SCAS_CHILD'
        JOIN (
          SELECT r2.user_id, MAX(r2.created_at) AS last_dt
          FROM responses r2
          JOIN surveys s2 ON s2.id=r2.survey_id AND s2.code='SCAS_CHILD'
          GROUP BY r2.user_id
        ) t ON t.user_id=r.user_id AND t.last_dt=r.created_at
      )
      SELECT ROUND(AVG(total_score), 0) AS avg_last FROM last
    """)
    return {
        "students": (st["c"] if st else 0) or 0,
        "attempts": (at["c"] if at else 0) or 0,
        "avg_last": (avg["avg_last"] if avg else 0) or 0,
    }

# acepta con y sin barra final para evitar 404
@bp.route("/students", methods=["GET"])
@bp.route("/students/", methods=["GET"])
@require_auth(role="admin")
def students():
    try:
        rows = _students_rows()
        return jsonify({"students": rows, "stats": _stats()})
    except Exception as e:
        # log opcional
        print("[ADMIN /students] error:", e)
        return jsonify({"error": "Error al obtener estudiantes"}), 500
