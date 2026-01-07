"""Populate the local Postgres DB with sample projects/videos."""
from __future__ import annotations

import random

from app import create_app
from app.extensions import db
from app.models import Project, Video
from app.services import project_service, video_service, inference_service

app = create_app()


def main() -> None:
    with app.app_context():
        projects = [
            {"name": "Brand Sweep", "description": "Retail storefront audit"},
            {"name": "Sponsorship Reel", "description": "Sports highlight review"},
        ]
        for payload in projects:
            project = Project.query.filter_by(name=payload["name"]).first()
            if not project:
                project = project_service.create_project(payload)
            print(f"Project ready: {project.id} - {project.name}")

            for idx in range(1, 3):
                source = f"/sample_videos/{project.id}_{idx}.mp4"
                existing = Video.query.filter_by(project_id=project.id, original_path=source).first()
                if existing:
                    video = existing
                else:
                    video = video_service.register_video(project.id, source)
                    video_service.probe_video_metadata(video)
                    video_service.generate_clips(video)
                print(f"  Video ready: video_id={video.id}")

                if random.random() > 0.5:
                    run = inference_service.run_inference(video, ["general-image-recognition"])
                    print(f"    Inference run: {run.id}")


if __name__ == "__main__":
    main()
