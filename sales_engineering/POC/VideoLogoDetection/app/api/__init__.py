"""API blueprint registration."""
from flask import Flask

from .projects import bp as projects_bp
from .videos import bp as videos_bp
from .metrics import bp as metrics_bp
from .clarifai import bp as clarifai_bp
from .vlm import bp as vlm_bp
from .reports import bp as reports_bp


def register_api_blueprints(app: Flask) -> None:
    app.register_blueprint(projects_bp)
    app.register_blueprint(videos_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(clarifai_bp)
    app.register_blueprint(vlm_bp)
    app.register_blueprint(reports_bp)
