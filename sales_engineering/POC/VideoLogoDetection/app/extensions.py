"""Flask extension singletons."""
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

from app.background_queue import BackgroundTaskQueue


db = SQLAlchemy()
socketio = SocketIO(async_mode="threading")
task_queue = BackgroundTaskQueue()
