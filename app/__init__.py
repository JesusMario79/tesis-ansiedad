# app/__init__.py
import os
from flask import Flask, send_from_directory

def create_app():
    app = Flask(
        __name__,
        static_folder="../public",
        template_folder="../public"
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    # Registrar blueprints si existen (auth, survey, admin)
    try:
        from . import auth, survey, admin
        for mod in (auth, survey, admin):
            if hasattr(mod, "bp"):
                app.register_blueprint(mod.bp)
    except Exception:
        pass

    # Páginas estáticas (sirven tus .html de /public)
    @app.get("/")
    def home():
        return send_from_directory(app.template_folder, "index.html")

    @app.get("/register")
    def register_page():
        return send_from_directory(app.template_folder, "register.html")

    @app.get("/student")
    def student_page():
        return send_from_directory(app.template_folder, "student.html")

    @app.get("/results")
    def results_page():
        return send_from_directory(app.template_folder, "results.html")

    @app.get("/admin")
    def admin_page():
        return send_from_directory(app.template_folder, "admin.html")

    return app
