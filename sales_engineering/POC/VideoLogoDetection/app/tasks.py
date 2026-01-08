"""Background tasks for RQ."""
from app import create_app
from app.extensions import db
from app.services import video_service, inference_service
from app.models import Video, InferenceRun

app = create_app()

def preprocess_video_task(video_id, options):
    with app.app_context():
        video = db.session.get(Video, video_id)
        if not video:
            return
        try:
            metadata = video_service.probe_video_metadata(video)
            if options.get("clips"):
                clips = video_service.generate_multiple_clips(video, options["clips"])
            else:
                clips = video_service.generate_clips(video, **options)
            video.status = "processed"
            db.session.commit()
        except Exception as e:
            video.status = "failed"
            db.session.commit()
            raise

def run_inference_task(run_id):
    with app.app_context():
        run = db.session.get(InferenceRun, run_id)
        if not run:
            return
        try:
            # Reconstruct request from run data
            from app.services.inference_models import InferenceRequest
            params = run.params or {}
            request = InferenceRequest(
                model_ids=run.model_ids,
                params=params.get("params", {}),
                clip_id=params.get("clip_id")
            )
            inference_service.run_inference(run.video, request)
        except Exception as e:
            run.status = "failed"
            run.results = {"error": str(e)}
            db.session.commit()
            raise