"""Word report generation helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from docx import Document

from app.extensions import db
from app.models import InferenceRun, Project, Video


def generate_video_report(project: Project, video: Video, inference_run: InferenceRun | None = None) -> Path:
    """Generate a minimal Word report summarizing detections for a video."""
    if inference_run is None:
        inference_run = (
            InferenceRun.query.filter_by(video_id=video.id, status="completed")
            .order_by(InferenceRun.created_at.desc())
            .first()
        )

    report_dir = Path("reports") / f"project_{project.id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"video_{video.id}_report_{timestamp}.docx"

    doc = Document()
    doc.add_heading(f"Video Logo Detection Report", level=1)

    # Project details
    doc.add_heading("Project", level=2)
    doc.add_paragraph(f"Name: {project.name}")
    doc.add_paragraph(f"Description: {project.description}")
    doc.add_paragraph(f"Budget Limit: {project.budget_limit} {project.currency}")

    # Video details
    doc.add_heading("Video", level=2)
    doc.add_paragraph(f"Video ID: {video.id}")
    doc.add_paragraph(f"Source: {video.original_path}")
    doc.add_paragraph(f"Resolution: {video.resolution or 'Unknown'}")
    doc.add_paragraph(f"Duration (s): {video.duration_seconds or 'Unknown'}")

    if inference_run is None:
        doc.add_paragraph("No inference runs available for this video.")
    else:
        doc.add_heading("Inference Summary", level=2)
        doc.add_paragraph(f"Run ID: {inference_run.id}")
        doc.add_paragraph(f"Status: {inference_run.status}")
        doc.add_paragraph(f"Models: {', '.join(inference_run.model_ids or [])}")

        detections_by_model: dict[str, list] = {}
        for detection in inference_run.detections:
            detections_by_model.setdefault(detection.model_id or "unknown", []).append(detection)

        for model_id, detections in detections_by_model.items():
            doc.add_heading(f"Model: {model_id}", level=3)
            table = doc.add_table(rows=1, cols=4)
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = "Frame"
            hdr_cells[1].text = "Timestamp (s)"
            hdr_cells[2].text = "Label"
            hdr_cells[3].text = "Confidence"
            for detection in detections:
                row_cells = table.add_row().cells
                row_cells[0].text = str(detection.frame_index or 0)
                row_cells[1].text = f"{float(detection.timestamp_seconds or 0):.2f}"
                row_cells[2].text = detection.label or ""
                row_cells[3].text = f"{float(detection.confidence or 0):.2f}"

    doc.save(report_path)
    db.session.commit()
    return report_path
