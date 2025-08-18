# app/__init__.py
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, jsonify

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC = BASE_DIR / "public"


def create_app():
    app = Flask(
        __name__,
        static_folder=str(PUBLIC),     # /public para css/js/imagenes
        template_folder=str(PUBLIC),   # html en /public
        static_url_path=""             # sirve /styles.css, /app.js, /favicon.ico
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    # -----------------------------------------
    # Blueprints
    # -----------------------------------------
    try:
        from . import auth, survey

        # /auth/login, /auth/register, /auth/me, etc.
        if hasattr(auth, "bp"):
            app.register_blueprint(auth.bp, url_prefix="/auth")

        # /api/survey/scas  y  /api/survey/scas/submit
        if hasattr(survey, "bp"):
            app.register_blueprint(survey.bp, url_prefix="/api/survey")

    except Exception as e:
        app.logger.debug(f"No se cargaron blueprints opcionales: {e}")

    # -----------------------------------------
    # Páginas HTML
    # -----------------------------------------
    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/register")
    @app.get("/register.html")
    def register_page():
        return render_template("register.html")

    @app.get("/student")
    @app.get("/student.html")
    def student_page():
        return render_template("student.html")

    @app.get("/results")
    @app.get("/results.html")
    def results_page():
        return render_template("results.html")

    @app.get("/admin")
    @app.get("/admin.html")
    def admin_page():
        return render_template("admin.html")

    # -----------------------------------------
    # API Admin: listado de estudiantes + stats
    # -----------------------------------------
    from .db import db_all
    from .utils import require_auth

    @app.get("/api/admin/students")
    @require_auth("admin")
    def api_admin_students():
        """
        Devuelve para cada estudiante:
          - attempts        : número de intentos (responses)
          - last_score      : total_score del último intento
          - last_level      : Bajo / Moderado / Alto (según last_score)
          - last_date       : fecha del último intento
        Y métricas globales para las tarjetas del dashboard.
        """
        rows = db_all(
            """
            SELECT
              u.id,
              u.fullname,
              u.email,
              COALESCE(COUNT(r.id), 0) AS attempts,
              (
                SELECT r2.total_score
                FROM responses r2
                WHERE r2.user_id = u.id
                ORDER BY r2.created_at DESC
                LIMIT 1
              ) AS last_score,
              MAX(r.created_at) AS last_date,
              u.created_at AS user_created
            FROM users u
            LEFT JOIN responses r ON r.user_id = u.id
            WHERE u.role = 'student'
            GROUP BY u.id
            """
        )

        # Orden: primero los que tienen fecha (más reciente), luego sin intentos.
        def _sort_key(rec):
            d = rec.get("last_date")
            if isinstance(d, datetime):
                # (0, -timestamp) => primero con fecha, más nuevo primero
                return (0, -int(d.timestamp()))
            return (1, 0)

        rows = sorted(rows, key=_sort_key)

        students = []
        attempts_total = 0
        last_scores = []

        for r in rows:
            attempts = int(r.get("attempts") or 0)
            attempts_total += attempts

            last_score = r.get("last_score")
            lvl = ""
            if last_score is not None:
                try:
                    last_score = int(last_score)
                    last_scores.append(last_score)
                    lvl = "Bajo" if last_score < 30 else ("Moderado" if last_score < 60 else "Alto")
                except Exception:
                    last_score = None
                    lvl = ""

            last_date = r.get("last_date")
            if isinstance(last_date, datetime):
                last_date_str = last_date.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_date_str = ""

            students.append({
                "fullname": r.get("fullname") or "",
                "email": r.get("email") or "",
                "attempts": attempts,
                "last_score": last_score,
                "last_level": lvl,
                "last_date": last_date_str,
            })

        avg_last = int(round(sum(last_scores) / len(last_scores))) if last_scores else 0

        stats = {
            "students": len(students),
            "attempts": attempts_total,
            "avg_last": avg_last,
        }
        return jsonify(ok=True, stats=stats, students=students)

    # -----------------------------------------
    # Fallback para archivos estáticos
    # -----------------------------------------
    @app.get("/<path:filename>")
    def public_files(filename):
        return send_from_directory(PUBLIC, filename)

    # -----------------------------------------
    # Inicialización de BD y seed al arrancar
    # -----------------------------------------
    try:
        from .db import create_database_if_needed, create_tables_if_needed, ensure_admin
        from .seed.seed_scas import run_seed  # crea/actualiza SCAS + sus 44 ítems

        with app.app_context():
            create_database_if_needed()
            create_tables_if_needed()
            ensure_admin()
            run_seed()
    except Exception as e:
        app.logger.error(f"Error inicializando la base de datos: {e}")

    return app
