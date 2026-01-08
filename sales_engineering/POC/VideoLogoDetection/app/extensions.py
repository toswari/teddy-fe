"""Flask extension singletons."""
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from redis import Redis
from rq import Queue


db = SQLAlchemy()
socketio = SocketIO(async_mode="threading")

# RQ setup
redis_conn = Redis()
task_queue = Queue(connection=redis_conn)
