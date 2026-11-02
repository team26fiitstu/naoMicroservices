import os
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    exercises_dir = os.environ.get("EXERCISES_DIR", "./data/exercises")
    dir_exists = os.path.isdir(exercises_dir)

    # Count how many exercises are stored
    exercise_count = 0
    if dir_exists:
        exercise_count = sum(
            1 for entry in os.scandir(exercises_dir)
            if entry.is_dir()
        )

    return jsonify({
        "status": "ok",
        "service": "ExerciseConfigService",
        "exercises_dir": exercises_dir,
        "exercises_dir_exists": dir_exists,
        "exercise_count": exercise_count,
    }), 200
