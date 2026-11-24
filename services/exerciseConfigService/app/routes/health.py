import os
from flask import Blueprint, jsonify

from app.choreography import choreography_count as count_choreographies

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    exercises_dir = os.environ.get("EXERCISES_DIR", "/exercises")
    dir_exists = os.path.isdir(exercises_dir)

    # Count how many exercises are stored (folders with a config.json;
    # the "_choreographies" directory has none and is skipped)
    exercise_count = 0
    if dir_exists:
        exercise_count = sum(
            1 for entry in os.scandir(exercises_dir)
            if entry.is_dir() and os.path.isfile(os.path.join(entry.path, "config.json"))
        )

    return jsonify({
        "status": "ok",
        "service": "ExerciseConfigService",
        "exercises_dir": exercises_dir,
        "exercises_dir_exists": dir_exists,
        "exercise_count": exercise_count,
        "choreography_count": count_choreographies(),
    }), 200