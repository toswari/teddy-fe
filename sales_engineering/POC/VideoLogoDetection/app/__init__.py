"""VideoLogoDetection Flask application factory."""
from __future__ import annotations

__version__ = "1.0.0"

import logging
import os
from pathlib import Path
from typing import Optional

from flask import Flask, render_template

from .config import get_config
from .extensions import db, socketio
from .api import register_api_blueprints
from .services.project_service import ensure_seed_project


def create_app(config_name: Optional[str] = None) -> Flask:
    """Application factory aligned with the single-user POC constraints."""
    app = Flask(
        __name__,
        static_folder=str(Path(__file__).resolve().parent.parent / "static"),
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
    )
    app.config.from_object(get_config(config_name))
    configure_logging(app)

    register_extensions(app)
    register_api_blueprints(app)
    register_cli(app)
    configure_shell_context(app)
    register_ui_routes(app)

    app.logger.debug("VideoLogoDetection app initialized with config=%s", app.config["LOG_LEVEL"])

    if app.config.get("AUTO_CREATE_SCHEMA", True):
        with app.app_context():
            db.create_all()
            ensure_seed_project()

    return app


def register_extensions(app: Flask) -> None:
    """Bind extensions declared in app.extensions."""
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    app.logger.debug("Extensions registered: SQLAlchemy + SocketIO")


def register_cli(app: Flask) -> None:
    """Provide helpful CLI commands for local dev."""

    @app.cli.command("seed")
    def seed() -> None:
        """Create the starter project if it does not exist."""
        ensure_seed_project()
        app.logger.info("Seed project ensured")


def configure_shell_context(app: Flask) -> None:
    from . import models

    @app.shell_context_processor
    def shell_context() -> dict[str, object]:
        """Expose handy objects when running `flask shell`."""
        return {"db": db, **models.__dict__}


def register_ui_routes(app: Flask) -> None:
    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/demo/detection-overlay")
    def detection_overlay():
        sample_detections = [
            {
                "label": "Metro-North Logo",
                "confidence": 0.91,
                "bbox": {"top": 0.32, "left": 0.19, "bottom": 0.58, "right": 0.47},
                "timestamp": "00:00:04.2",
                "color": "#22d3ee",
            },
            {
                "label": "Station Placard",
                "confidence": 0.74,
                "bbox": {"top": 0.41, "left": 0.53, "bottom": 0.77, "right": 0.88},
                "timestamp": "00:00:04.2",
                "color": "#f97316",
            },
        ]
        sample_image_url = app.config.get(
            "CLARIFAI_SAMPLE_IMAGE_URL",
            os.getenv("CLARIFAI_TEST_IMAGE", "https://samples.clarifai.com/metro-north.jpg"),
        )
        return render_template(
            "mock_detection_overlay.html",
            sample_image_url=sample_image_url,
            detections=sample_detections,
        )


def configure_logging(app: Flask) -> None:
    """Configure basic logging for local development clarity."""
    log_level = app.config.get("LOG_LEVEL", "DEBUG").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.DEBUG))
    app.logger.setLevel(log_level)
