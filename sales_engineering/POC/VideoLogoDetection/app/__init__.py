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
    
    # Disable caching in debug mode to prevent stale templates/assets
    @app.after_request
    def add_no_cache_headers(response):
        if app.debug:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response
    
    app.logger.debug("Extensions registered: SQLAlchemy + SocketIO")


def register_cli(app: Flask) -> None:
    """Provide helpful CLI commands for local dev."""

    @app.cli.command("seed")
    def seed() -> None:
        """Create the starter project if it does not exist."""
        ensure_seed_project()
        app.logger.info("Seed project ensured")

    @app.cli.command("cleanup")
    def cleanup() -> None:
        """Clean up orphaned files in media directory."""
        from pathlib import Path
        from app.models import Video, InferenceRun
        media_root = Path(app.config.get("PROJECT_MEDIA_ROOT", "media"))
        if not media_root.is_absolute():
            media_root = Path(app.root_path).parent / media_root
        
        # Get all existing video and run paths from DB
        existing_paths = set()
        videos = Video.query.all()
        for video in videos:
            if video.storage_path:
                existing_paths.add(Path(video.storage_path).resolve())
            if video.video_metadata and "clips" in video.video_metadata:
                for clip in video.video_metadata["clips"]:
                    if "path" in clip:
                        existing_paths.add(Path(clip["path"]).resolve())
        
        runs = InferenceRun.query.all()
        for run in runs:
            if run.results and "frames" in run.results:
                for frame in run.results["frames"]:
                    if "image_path" in frame:
                        existing_paths.add(Path(frame["image_path"]).resolve())
        
        # Walk media directory and remove files not in existing_paths
        removed = 0
        for path in media_root.rglob("*"):
            if path.is_file() and path.resolve() not in existing_paths:
                path.unlink()
                removed += 1
        app.logger.info("Cleanup completed, removed %s orphaned files", removed)


def configure_shell_context(app: Flask) -> None:
    from . import models

    @app.shell_context_processor
    def shell_context() -> dict[str, object]:
        """Expose handy objects when running `flask shell`."""
        return {"db": db, **models.__dict__}


def register_ui_routes(app: Flask) -> None:
    @app.route("/health")
    def health():
        try:
            db.engine.execute("SELECT 1")
            return {"status": "healthy", "database": "connected"}
        except Exception as e:
            app.logger.error("Health check failed: %s", e)
            return {"status": "unhealthy", "database": "disconnected"}, 500

    @app.route("/")
    def dashboard():
        return render_template("dashboard-inference.html")

    @app.route("/preprocessing")
    def preprocessing():
        return render_template("dashboard-preprocessing.html")

    @app.route("/preprocess")
    def preprocess():
        return render_template("preprocess.html")

    @app.route("/media/<int:project_id>/<int:video_id>/<path:filename>")
    def serve_media(project_id: int, video_id: int, filename: str):
        from flask import send_from_directory
        media_root = Path(app.config.get("PROJECT_MEDIA_ROOT", "media"))
        if not media_root.is_absolute():
            media_root = Path(app.root_path).parent / media_root
        video_dir = media_root / f"project_{project_id}" / f"video_{video_id}"
        return send_from_directory(video_dir, filename)

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
