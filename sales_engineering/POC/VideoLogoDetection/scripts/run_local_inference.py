"""Register a local video, create clips, and run inference once.

This helper keeps the in-process Clarifai stub path working so developers can
quickly verify the full inference pipeline (DB + sampling + detections) without
wiring the UI. Provide an absolute path to a video file or rely on the bundled
sample under ``media/project_1/video_1/video_1_sample.mp4``.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from app import create_app
from app.extensions import db
from app.models import Project, Video
from app.services import inference_service, project_service, video_service
from app.services.inference_models import InferenceParams, InferenceRequest
from app.services.metrics_service import summarize_run_models

DEFAULT_PROJECT_NAME = "Local Demo Project"
DEFAULT_VIDEO_PATH = Path("media/project_1/video_1/video_1_sample.mp4")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Clarifai inference stub once")
    parser.add_argument(
        "--project-name",
        default=DEFAULT_PROJECT_NAME,
        help=f"Project name to reuse/create (default: {DEFAULT_PROJECT_NAME})",
    )
    parser.add_argument(
        "--project-description",
        default="Local verification project",
        help="Description used when creating the project",
    )
    parser.add_argument(
        "--video",
        dest="video_path",
        default=str(DEFAULT_VIDEO_PATH),
        help="Path to an MP4 to ingest (default: bundled sample video)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["general-image-recognition"],
        help="One or more Clarifai model identifiers",
    )
    parser.add_argument(
        "--clip-id",
        dest="clip_id",
        default=None,
        help="Clip identifier (e.g., '12-1'). Defaults to first generated clip",
    )
    parser.add_argument("--fps", type=float, default=None, help="Override sampling FPS")
    parser.add_argument(
        "--min-confidence",
        dest="min_confidence",
        type=float,
        default=None,
        help="Override minimum confidence",
    )
    parser.add_argument(
        "--max-concepts",
        dest="max_concepts",
        type=int,
        default=None,
        help="Override maximum concepts",
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=None,
        help="Override Clarifai batch size",
    )
    return parser.parse_args()


def ensure_project(name: str, description: str) -> Project:
    project = Project.query.filter_by(name=name).first()
    if project:
        return project
    return project_service.create_project({"name": name, "description": description})


def _looks_like_clip_file(path: Path) -> bool:
    name = path.name.lower()
    return "clips" in path.parts or "-clip" in name or name.startswith("clip")


def _attach_synthetic_clip(video: Video) -> list[dict[str, Any]]:
    duration = float(video.duration_seconds or 0)
    storage_path = video.storage_path or video.original_path
    absolute_path = str((Path.cwd() / storage_path).resolve())
    clip_entry = {
        "path": absolute_path,
        "start": 0.0,
        "end": duration or None,
        "segment": 1,
        "duration": duration or None,
    }
    metadata = {**(video.video_metadata or {}), "clips": [clip_entry]}
    video.video_metadata = metadata
    db.session.commit()
    return metadata["clips"]


def ensure_video(project: Project, source_path: Path) -> Video:
    source = source_path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Video file not found: {source}")

    source_is_clip = _looks_like_clip_file(source)
    video = Video.query.filter_by(project_id=project.id, original_path=str(source)).first()
    if not video:
        video = video_service.register_video(project.id, str(source))
    if not video.duration_seconds:
        video_service.probe_video_metadata(video)
    clip_entries = (video.video_metadata or {}).get("clips")
    if not clip_entries:
        if source_is_clip:
            clip_entries = _attach_synthetic_clip(video)
        else:
            video_service.generate_clips(video)
    return video


def build_params(args: argparse.Namespace) -> InferenceParams:
    overrides = {}
    if args.fps is not None:
        overrides["fps"] = args.fps
    if args.min_confidence is not None:
        overrides["min_confidence"] = args.min_confidence
    if args.max_concepts is not None:
        overrides["max_concepts"] = args.max_concepts
    if args.batch_size is not None:
        overrides["batch_size"] = args.batch_size
    if overrides:
        return InferenceParams(**overrides)
    return InferenceParams()


def pick_clip_id(video: Video, requested: str | None) -> str | None:
    if requested:
        return requested
    clip_entries = (video.video_metadata or {}).get("clips") or []
    if not clip_entries:
        return None
    first_segment = clip_entries[0].get("segment") or 1
    return f"{video.id}-{first_segment}"


def summarize_run(run) -> str:
    ordered, counts = summarize_run_models(run)
    parts = [f"Run {run.id} · status={run.status}"]
    parts.append("Models: " + ", ".join(ordered))
    parts.append(
        "Detection counts: "
        + ", ".join(f"{model}={counts.get(model, 0)}" for model in ordered)
    )
    return " | ".join(parts)


def run_once(models: Sequence[str], clip_id: str | None, params: InferenceParams, video: Video):
    request = InferenceRequest(model_ids=list(models), clip_id=clip_id, params=params)
    run = inference_service.run_inference(video, request)
    db.session.refresh(run)
    return run


def main() -> None:
    args = parse_args()
    app = create_app()
    with app.app_context():
        project = ensure_project(args.project_name, args.project_description)
        video = ensure_video(project, Path(args.video_path))
        clip_id = pick_clip_id(video, args.clip_id)
        params = build_params(args)
        run = run_once(args.models, clip_id, params, video)
        print("Inference complete:")
        print("  " + summarize_run(run))
        if clip_id:
            print(f"  Clip: {clip_id}")
        print(
            "  Frames sampled:",
            (run.results or {}).get("frames_sampled"),
        )
        print(
            "  Frames stored:",
            len((run.results or {}).get("frames") or []),
        )


if __name__ == "__main__":
    main()
