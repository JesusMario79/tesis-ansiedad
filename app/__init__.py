# app/__init__.py
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory
from flask_cors import CORS

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC = BASE_DIR / "public"

def create_app():
    app = Flask(
        __name__,
        static_folder=str(PUBLIC),
        template_folder=str(PUBLIC),
        static_url_path=""
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    CORS(
        app,
        resources={
            r"/auth/*": {"origins": [
                "https://jesusmario79.github.io",
                "http://127.0.0.1:5000", "http://localhost:5000"
            ]},
            r"/api/*": {"origins": [
                "https://jesusmario79.github.io",
                "http://127.0.0.1:5000", "http://localhost:5000"
            ]},
        },
        supports_credentials=True,
    )

    # Blueprints (cada uno ya trae url_prefix)
    from . import auth, survey, admin
    app.register_blueprint(auth.bp)    # /auth/...
    app.register_blueprint(survey.bp)  # /api/survey/...
    app.register_blueprint(admin.bp)   # /api/admin/...

    # Páginas estáticas útiles en local
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

    @app.get("/<path:filename>")
    def public_files(filename):
        return send_from_directory(PUBLIC, filename)

    # Inicialización DB/seed
    from .db import create_database_if_needed, create_tables_if_needed, ensure_admin
    from .seed.seed_scas import run_seed
    with app.app_context():
        create_database_if_needed()
        create_tables_if_needed()
        ensure_admin()
        run_seed()

    print(app.url_map)
    return app
