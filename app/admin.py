# app/admin.py
from __future__ import annotations

from flask import Blueprint, jsonify
from .db import db_all, db_one
from .utils import require_auth, level_from_score

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _survey_id():
    s = db_one("SELECT id FROM surveys WHERE code='SCAS_CHILD'")
    return s["id"] if s else None


def _students_rows(sid: int):
    # “last”: último intento por alumno; “agg”: total de intentos por alumno
    sql = """
    WITH last AS (
        SELECT r.user_id, r.total_score, r.created_at
        FROM responses r
        JOIN (
            SELECT user_id, MAX(created_at) AS last_dt
            FROM responses
            WHERE survey_id=:sid
            GROUP BY user_id
        ) t ON t.user_id = r.user_id AND t.last_dt = r.created_at
        WHERE r.survey_id=:sid
    ),
    agg AS (
        SELECT user_id, COUNT(*) AS attempts
        FROM responses
        WHERE survey_id=:sid
        GROUP BY user_id
    )
    SELECT
        u.fullname,
        u.email,
        COALESCE(a.attempts, 0)        AS attempts,
        l.total_score                  AS last_score,
        l.created_at                   AS last_date
    FROM users u
    LEFT JOIN agg a  ON a.user_id = u.id
    LEFT JOIN last l ON l.user_id = u.id
    WHERE
        u.role = 'student' OR
        u.id IN (SELECT DISTINCT user_id FROM responses WHERE survey_id=:sid)
    ORDER BY COALESCE(l.created_at, TIMESTAMP('1970-01-01 00:00:00')) DESC,
             u.fullname ASC
    """
    rows = db_all(sql, {"sid": sid})
    out = []
    for r in rows:
        d = dict(r)
        d["last_level"] = (
            level_from_score(d["last_score"]) if d["last_score"] is not None else None
        )
        out.append(d)
    return out


def _stats(sid: int):
    # Alumnos = distintos usuarios que han respondido o que tienen role student
    students = db_one(
        """
        SELECT
          (
            SELECT COUNT(*) FROM users WHERE role='student'
          ) +
          (
            SELECT COUNT(*) FROM (
              SELECT DISTINCT user_id
              FROM responses WHERE survey_id=:sid
            ) z
          ) -
          (
            SELECT COUNT(*) FROM users u
            WHERE u.role='student' AND u.id IN (
              SELECT DISTINCT user_id FROM responses WHERE survey_id=:sid
            )
          ) AS c
        """,
        {"sid": sid},
    )["c"] or 0

    attempts = db_one(
        "SELECT COUNT(*) AS c FROM responses WHERE survey_id=:sid", {"sid": sid}
    )["c"] or 0

    avg_last = db_one(
        """
        WITH last AS (
          SELECT r.user_id, r.total_score
          FROM responses r
          JOIN (
            SELECT user_id, MAX(created_at) AS last_dt
            FROM responses
            WHERE survey_id=:sid
            GROUP BY user_id
          ) t ON t.user_id=r.user_id AND t.last_dt=r.created_at
          WHERE r.survey_id=:sid
        )
        SELECT ROUND(AVG(total_score),0) AS avg_last FROM last
        """,
        {"sid": sid},
    )["avg_last"] or 0

    return {"students": students, "attempts": attempts, "avg_last": avg_last}


@bp.get("/students")
@bp.get("/students/")
@require_auth(role="admin")
def students():
    sid = _survey_id()
    if not sid:
        return jsonify({"students": [], "stats": {"students": 0, "attempts": 0, "avg_last": 0}})
    try:
        rows = _students_rows(sid)
        return jsonify({"students": rows, "stats": _stats(sid)})
    except Exception as e:
        print("[ADMIN /students] error:", e)
        return jsonify({"error": "Error al obtener estudiantes"}), 500
