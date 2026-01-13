"""Report export API endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, request, send_file

from app.extensions import db
from app.models import InferenceRun
from app.services import reporting_service
from app.services.reporting_service import ReportExportError

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _build_archive_response(run: InferenceRun, regenerate: bool):
    if run.status != "completed":
        return {"error": "Inference run is not completed yet."}, 409

    try:
        archive_path = reporting_service.build_run_export(run, regenerate=regenerate)
    except ReportExportError as exc:
        return {"error": str(exc)}, 400
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Run export build failed (run_id=%s)", run.id, exc_info=exc)
        return {"error": "Failed to build run export."}, 500

    if not archive_path.is_file():
        return {"error": "Run export not found."}, 404

    return send_file(
        str(archive_path),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"run_{run.id}.zip",
    )


@bp.get("/run/<int:run_id>/download")
def download_run_archive(run_id: int):
    run = db.session.get(InferenceRun, run_id)
    if run is None:
        return {"error": "Inference run not found"}, 404

    regenerate = request.args.get("regenerate", "false").lower() == "true"
    return _build_archive_response(run, regenerate)
