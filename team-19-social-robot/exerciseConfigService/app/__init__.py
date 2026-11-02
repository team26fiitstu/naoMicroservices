import os
from flask import Flask


def create_app():
    app = Flask(__name__)

    # Ensure the exercises directory exists on startup
    exercises_dir = os.environ.get("EXERCISES_DIR", "./data/exercises")
    os.makedirs(exercises_dir, exist_ok=True)

    from .routes.health import health_bp
    from .routes.exercise import exercise_bp
    from .routes.voice_lines_for_robot import voice_lines_bp 
    app.register_blueprint(health_bp)
    app.register_blueprint(exercise_bp)
    app.register_blueprint(voice_lines_bp)
   
    return app
