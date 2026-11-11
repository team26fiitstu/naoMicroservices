import os
import json
import requests
from flask import Blueprint, request, jsonify, send_file
import io

from app.storage import (
    exercise_exists,
    get_frame,
)

from app.voice_lines import (
    get_voice_lines_from_frame_config,
    insert_voice_lines_into_frame_config,
    delete_voice_line_from_frame_config,
    get_voice_lines_sound,
    delete_voice_lines_sound,
    insert_voice_lines_sound
)
voice_lines_bp = Blueprint("voiceLines", __name__, url_prefix="/voiceLines")

# ---------------------------------------------------------------------------
# GET /voiceLines/conf
# ---------------------------------------------------------------------------
@voice_lines_bp.route("/conf", methods=["GET"])
def get():
    return jsonify({"OK": "hh"}), 200

    
    

# ---------------------------------------------------------------------------
# GET /voiceLines/config/exercise/<exercise_id>/frame/<int:frame_index>
# ---------------------------------------------------------------------------
@voice_lines_bp.route("/config/exercise/<exercise_id>/frame/<int:frame_index>", methods=["GET"])
def get_voice_lines_config_for_frame_api(exercise_id, frame_index):
    if not exercise_exists(exercise_id):
        return jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404
    try:
        frame_config = get_frame(exercise_id, frame_index)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    if voice_lines_config := get_voice_lines_from_frame_config(exercise_id, frame_index):
        return jsonify(voice_lines_config), 200
    return jsonify({}), 200


# ---------------------------------------------------------------------------
# POST /voiceLines/config/exercise/<exercise_id>/frame/<int:frame_index>
# ---------------------------------------------------------------------------
@voice_lines_bp.route("/config/exercise/<exercise_id>/frame/<int:frame_index>", methods=["POST"])
def insert_voice_lines_config_for_frame_api(exercise_id, frame_index):
    if not exercise_exists(exercise_id):
        return jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404
    if request.content_type and "multipart/form-data" in request.content_type:
        voice_lines_config = request.form.get("voice_lines")
    else:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON body or multipart/form-data required"}), 400
        voice_lines_config = data.get("voice_lines")
    insert_voice_lines_into_frame_config(exercise_id, frame_index, voice_lines_config)
    return jsonify({"error": "Voice config sucessfully inserted."}), 200


# ---------------------------------------------------------------------------
# GET /voiceLines/sound/exercise/<exercise_id>/frame/<int:frame_index>/<file_name>
# ---------------------------------------------------------------------------
@voice_lines_bp.route("/sound/exercise/<exercise_id>/frame/<int:frame_index>/<file_name>", methods=["GET"])
def get_voice_lines_sound_api(exercise_id, frame_index, file_name):
    if not exercise_exists(exercise_id):
        return jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404
    try:
        frame_config = get_frame(exercise_id, frame_index)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    if voice_lines_sound_in_base64 := get_voice_lines_sound(exercise_id, frame_index, file_name):
        return jsonify({"sound": voice_lines_sound_in_base64, "audioFormat": "webm"}), 200
    return jsonify({"error": "No file extracted."}), 400


# ---------------------------------------------------------------------------
# DELETE /voiceLines/sound/exercise/<exercise_id>/frame/<int:frame_index>/<file_name>
# ---------------------------------------------------------------------------
@voice_lines_bp.route("/sound/exercise/<exercise_id>/frame/<int:frame_index>/<file_name>", methods=["DELETE"])
def delete_voice_lines_sound_api(exercise_id, frame_index, file_name):
    if not exercise_exists(exercise_id):
        return jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404
    try:
        frame_config = get_frame(exercise_id, frame_index)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    if delete_voice_lines_sound(exercise_id, frame_index, file_name):
        if delete_voice_line_from_frame_config(exercise_id, frame_index, file_name):
            return jsonify({"result": "OK", "audioFormat": "webm"}), 200
        return jsonify({"error": "File removed but cannot remove from file config."}), 400
    return jsonify({"error": "No file extracted."}), 400
    

# ---------------------------------------------------------------------------
# POST /voiceLines/sound/exercise/<exercise_id>/frame/<int:frame_index>
# ---------------------------------------------------------------------------
@voice_lines_bp.route("/sound/exercise/<exercise_id>/frame/<int:frame_index>", methods=["POST"])
def insert_voice_lines_sound_api(exercise_id, frame_index):
    if not exercise_exists(exercise_id):
        return jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404
    if request.content_type and "multipart/form-data" in request.content_type:
        sound_in_base64 = request.form.get("sound")
        file_name = request.form.get("file_name")
    else:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON body or multipart/form-data required"}), 400
        sound_in_base64 = data.get("sound")
        file_name = data.get("file_name")
    insert_voice_lines_sound(exercise_id, frame_index, sound_in_base64, file_name)
    return jsonify({"error": "Voice config successfully inserted."}), 200


