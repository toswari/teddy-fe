"""RQ worker for background tasks."""
from app import create_app
from app.extensions import task_queue

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        worker = task_queue.Worker([task_queue])
        worker.work()