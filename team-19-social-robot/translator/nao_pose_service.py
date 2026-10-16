#!/usr/bin/env python3
"""
nao_pose_service.py

Flask microservice that:
    - /arms/from_image: accept a single image, compute pose, send to NAO.
    - /arms/from_video: accept a video, split into frames via pose_from_video,
                        filter incomplete frames, send each valid pose to NAO,
                        save debug frame images.
"""

import os
import uuid
import json

from flask import Flask, request, jsonify
import requests

from arms_translator import translate_arms
from video_pose_processor import process_video_bytes
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()


# =========================
# CONFIG
# =========================

NO_NAMING = os.environ.get('NO_NAMING', True)
if NO_NAMING:
    POSE_API_URL = "http://localhost:6001/media_pipe_pose/pose_from_image"
    SET_POSE_URL = "http://localhost:5000/setting_pose/setPose"
    VOICE_LINES_URL = "http://localhost:5000/voiceLines/applyVoiceLine"
    EXERCISE_CONFIG_URL = os.environ.get("EXERCISE_CONFIG_URL", "http://localhost:7001")
else:
    POSE_API_URL = "http://skeletonfinderapi:6001/media_pipe_pose/pose_from_image"
    SET_POSE_URL = "http://naorobotapi:5000/setting_pose/setPose"
    VOICE_LINES_URL = "http://naorobotapi:5000/voiceLines/applyVoiceLine"
    EXERCISE_CONFIG_URL = os.environ.get("EXERCISE_CONFIG_URL", "http://exerciseconfigservice:7001")

# Host directory mounted into pose container as /images
POSE_HOST_ROOT = "/home/ubuntu/Pictures"      # host/VM path
POSE_CONT_ROOT = "/images"                    # container path

# Subdir for single-image uploads (used by /arms/from_image)
UPLOAD_SUBDIR = "nao_pose_uploads"
UPLOAD_DIR = os.path.join(POSE_HOST_ROOT, UPLOAD_SUBDIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Root dir for video debug frames (host only; not used by pose container)
VIDEO_FRAMES_ROOT = os.path.join(POSE_HOST_ROOT, "nao_video_frames")
os.makedirs(VIDEO_FRAMES_ROOT, exist_ok=True)

app = Flask(__name__)
CORS(app) #added

# =========================
# HELPERS
# =========================
def call_pose_service(container_path: str):
    """
    Call the MediaPipe pose_from_image API with a file path
    (as seen inside the pose container) and return landmarks.
    """
    params = {"file_location": container_path}
    resp = requests.get(POSE_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    required_joints = [
        "Left shoulder",
        "Right shoulder",
        "Left elbow",
        "Right elbow",
        "Left wrist",
        "Right wrist",
    ]
    required_coords = ["x", "y", "z"]

    for joint in required_joints:
        if joint not in data:
            raise KeyError(f"Missing landmark: {joint}")
        for c in required_coords:
            if c not in data[joint]:
                raise KeyError(f"Missing coordinate '{c}' for {joint}")

    return data


def call_exercise_create(name, frames, pose_engine="mediapipe", media_bytes=None, media_ext=".mp4"):
    """
    POST to exerciseconfigservice /exercise/create.
    Sends frames as JSON form field, optionally attaches media file.
    Returns the created exercise config dict.
    """
    data = {
        "name": (None, name),
        "pose_engine": (None, pose_engine),
        "frames": (None, json.dumps(frames), "application/json"),
    }
    if media_bytes is not None:
        ext = media_ext if media_ext.startswith(".") else f".{media_ext}"
        data["media"] = (f"original{ext}", media_bytes, "application/octet-stream")

    resp = requests.post(f"{EXERCISE_CONFIG_URL}/exercise/create", files=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def call_nao_set_pose(angles):
    """
    Call NAO pose endpoint with the given angles.
    """
    payload = {"angles": angles}
    resp = requests.post(SET_POSE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def call_nao_voice_lines(voice_lines_configs):
    """
    Call NAO to say voice line.
    """
    payload = {"voice_lines": voice_lines_configs}
    resp = requests.post(VOICE_LINES_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()
    

# =========================
# ROUTES
# =========================

@app.route("/test", methods=["GET"])
def test():
    return "NAO Pose Service is running."

@app.route("/arms/from_landmarks", methods=["POST"])
def arms_from_landmarks():
    """
    Accept raw xyz landmarks, return keypoints + NAO angles. No robot call.

    Request (JSON):
        {
            "Left shoulder":  {"x": 0.60, "y": 0.41, "z": -0.30},
            "Right shoulder": {"x": 0.42, "y": 0.36, "z": -0.31},
            "Left elbow":     {"x": 0.62, "y": 0.53, "z": -0.24},
            "Right elbow":    {"x": 0.36, "y": 0.26, "z": -0.41},
            "Left wrist":     {"x": 0.61, "y": 0.63, "z": -0.28},
            "Right wrist":    {"x": 0.32, "y": 0.11, "z": -0.43},
            ...any extra landmarks are stored but not used for angles
        }

    Response (JSON):
        {
            "keypoints": { ...full input landmarks... },
            "nao_angles": [LShoulderPitch, LShoulderRoll, LElbowRoll, LElbowYaw, ...],
            "joint_values": {"LShoulderPitch": ..., "LShoulderRoll": ..., ...}
        }
    """
    landmarks = request.get_json(silent=True)
    if not landmarks:
        return jsonify({"error": "JSON body with landmarks required"}), 400

    required = ["Left shoulder", "Right shoulder", "Left elbow",
                "Right elbow", "Left wrist", "Right wrist"]
    for joint in required:
        if joint not in landmarks:
            return jsonify({"error": f"Missing required landmark: '{joint}'"}), 400

    try:
        result = translate_arms(landmarks)
    except Exception as e:
        return jsonify({"error": "failed to translate landmarks to NAO angles", "detail": str(e)}), 500

    joint_keys = [
        "LShoulderPitch", "LShoulderRoll", "LElbowRoll", "LElbowYaw",
        "RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RElbowYaw",
    ]

    return jsonify({
        "keypoints": landmarks,
        "nao_angles": result["angles"],
        "joint_values": {k: result[k] for k in joint_keys},
    }), 200


@app.route("/exercise/from_image", methods=["POST"])
def exercise_from_image():
    """
    Full upload flow: image → skeleton → angles → save exercise.

    Request (multipart/form-data):
        image: file
        name:  string (default "Unnamed Exercise")

    Response:
        201 JSON: exercise config
    """
    if "image" not in request.files:
        return jsonify({"error": "image file is required (field 'image')"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    name = request.form.get("name", "Unnamed Exercise")
    ext = os.path.splitext(file.filename)[1] or ".jpg"

    try:
        image_bytes = file.read()
    except Exception as e:
        return jsonify({"error": "failed to read image", "detail": str(e)}), 500

    # 1) Get landmarks from skeletonfinderapi via base64 POST
    import base64
    try:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        resp = requests.post(
            POSE_API_URL,
            data=encoded,
            headers={"Content-Type": "text/plain"},
            timeout=15,
        )
        resp.raise_for_status()
        landmarks = resp.json()
    except requests.RequestException as e:
        return jsonify({"error": "failed to call skeletonfinderapi", "detail": str(e)}), 502

    required = ["Left shoulder", "Right shoulder", "Left elbow", "Right elbow", "Left wrist", "Right wrist"]
    for joint in required:
        if joint not in landmarks:
            return jsonify({"error": f"incomplete pose — missing landmark: '{joint}'"}), 422

    # 2) Translate landmarks → NAO angles
    try:
        result = translate_arms(landmarks)
    except Exception as e:
        return jsonify({"error": "failed to translate landmarks", "detail": str(e)}), 500

    # 3) Save exercise in exerciseconfigservice
    try:
        config = call_exercise_create(
            name=name,
            frames=[{"keypoints": landmarks, "nao_angles": result["angles"]}],
            pose_engine="mediapipe",
            media_bytes=image_bytes,
            media_ext=ext,
        )
    except requests.RequestException as e:
        return jsonify({"error": "failed to save exercise", "detail": str(e)}), 502

    return jsonify(config), 201


@app.route("/arms/from_image", methods=["POST"])
def arms_from_image():
    """
    Accept an image, compute NAO arm pose, and send it to NAO.

    Request:
        multipart/form-data
        image: file

    Response:
        200 JSON with angles, joint values, debug paths
        4xx/5xx error JSON otherwise
    """
    if "image" not in request.files:
        return jsonify({"error": "image file is required (multipart/form-data, field 'image')"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    # Save file on host in /home/noetic/Pictures/nao_pose_uploads
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    tmp_name = f"{uuid.uuid4().hex}{ext}"
    host_path = os.path.join(UPLOAD_DIR, tmp_name)

    try:
        file.save(host_path)
    except Exception as e:
        return jsonify({"error": "failed to save uploaded file", "detail": str(e)}), 500

    # Path as seen inside the pose container
    container_path = os.path.join(POSE_CONT_ROOT, UPLOAD_SUBDIR, tmp_name)

    # 1) Pose estimation
    try:
        landmarks = call_pose_service(container_path)
    except requests.RequestException as e:
        return jsonify({
            "error": "failed to call pose service",
            "detail": str(e),
            "file_location_pose_container": container_path,
            "file_location_host": host_path,
        }), 502
    except KeyError as e:
        return jsonify({
            "error": "pose not detected or incomplete (missing landmarks)",
            "detail": str(e),
            "file_location_pose_container": container_path,
            "file_location_host": host_path,
        }), 422

    # 2) Translate landmarks -> NAO angles
    try:
        result = translate_arms(landmarks)
        angles = result["angles"]
    except Exception as e:
        return jsonify({
            "error": "failed to translate landmarks to NAO angles",
            "detail": str(e),
        }), 500

    # Optional: treat all-zero as "no useful pose"
    if all(abs(a) < 1e-4 for a in angles):
        return jsonify({
            "error": "image did not produce usable NAO angles (all ~0)",
        }), 422

    # 3) Send to NAO
    try:
        nao_response = call_nao_set_pose(angles)
    except requests.RequestException as e:
        return jsonify({
            "error": "failed to send pose to NAO",
            "detail": str(e),
        }), 502

    joint_keys = [
        "LShoulderPitch",
        "LShoulderRoll",
        "LElbowRoll",
        "LElbowYaw",
        "RShoulderPitch",
        "RShoulderRoll",
        "RElbowRoll",
        "RElbowYaw",
    ]

    return jsonify({
        "file_location_host": host_path,
        "file_location_pose_container": container_path,
        "nao_angles": [float(a) for a in angles],
        "joint_values": {k: float(result[k]) for k in joint_keys},
        "nao_response": nao_response,
    })


@app.route("/exercise/<exercise_id>/run", methods=["POST"])
def exercise_run(exercise_id):
    """
    Run a saved exercise on the NAO robot.

    Request (JSON, optional):
        {"repetitions": 3}   ← overrides value stored in config

    Response:
        200 JSON: {exercise_id, repetitions, frames_per_rep, total_poses_sent, results[]}
    """
    data = request.get_json(silent=True) or {}

    # 1) Fetch frames from exerciseconfigservice
    try:
        resp = requests.get(f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/frames", timeout=10)
        if resp.status_code == 404:
            return jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404
        resp.raise_for_status()
        frames = resp.json()
    except requests.RequestException as e:
        return jsonify({"error": "failed to fetch frames", "detail": str(e)}), 502

    if not frames:
        return jsonify({"error": "exercise has no frames"}), 422

    # 2) Get repetitions from config (or override from request)
    repetitions = data.get("repetitions")
    if repetitions is None:
        try:
            cfg_resp = requests.get(f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}", timeout=10)
            cfg_resp.raise_for_status()
            repetitions = cfg_resp.json().get("repetitions", 1)
        except requests.RequestException as e:
            return jsonify({"error": "failed to fetch exercise config", "detail": str(e)}), 502

    try:
        repetitions = int(repetitions)
        if repetitions < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "repetitions must be a positive integer"}), 400

    # 3) Loop repetitions × frames → send each to NAO
    results = []
    for rep in range(repetitions):
        for frame in frames:
            if voice_lines := frame.get("voice_lines"):
                try:
                    nao_response = call_nao_voice_lines(voice_lines)
                    results.append({"rep": rep, "type": "pose", "frame_index": frame.get("frame_index"), "status": "ok"})
                except requests.RequestException as e:
                    results.append({"rep": rep, "type": "voice", "frame_index": frame.get("frame_index"), "status": "error", "detail": str(e)})
            angles = frame.get("nao_angles", [])
            try:
                nao_response = call_nao_set_pose(angles)
                results.append({"rep": rep, "type": "pose", "frame_index": frame.get("frame_index"), "status": "ok"})
            except requests.RequestException as e:
                results.append({"rep": rep, "type": "pose", "frame_index": frame.get("frame_index"), "status": "error", "detail": str(e)})

    return jsonify({
        "exercise_id": exercise_id,
        "repetitions": repetitions,
        "frames_per_rep": len(frames),
        "total_poses_sent": len(results),
        "results": results,
    }), 200


@app.route("/exercise/from_video", methods=["POST"])
def exercise_from_video():
    """
    Full upload flow: video → skeleton → angles → save exercise.

    Request (multipart/form-data):
        video:   file
        name:    string (default "Unnamed Exercise")
        fps:     int    (default 1)
        seconds: int    (default -1, full video)

    Response:
        201 JSON: exercise config + frame_count
    """
    if "video" not in request.files:
        return jsonify({"error": "video file is required (field 'video')"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    name = request.form.get("name", "Unnamed Exercise")

    try:
        fps = int(request.form.get("fps", "1"))
        seconds = int(request.form.get("seconds", "-1"))
        max_frames = int(request.form.get("max_frames", "-1"))
    except ValueError:
        return jsonify({"error": "fps, seconds, and max_frames must be integers"}), 400

    try:
        video_bytes = file.read()
    except Exception as e:
        return jsonify({"error": "failed to read video", "detail": str(e)}), 500

    ext = os.path.splitext(file.filename)[1] or ".mp4"
    upload_id = uuid.uuid4().hex
    output_dir = os.path.join(VIDEO_FRAMES_ROOT, upload_id)

    # 1) Get landmarks from skeletonfinderapi
    try:
        summary = process_video_bytes(
            video_bytes=video_bytes,
            output_dir=output_dir,
            number_frames_per_sec=fps,
            number_seconds_to_process=seconds,
            attach_visualization=True,
        )
    except requests.RequestException as e:
        return jsonify({"error": "failed to call skeletonfinderapi", "detail": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "failed to process video", "detail": str(e)}), 500

    if summary["valid_frames"] == 0:
        return jsonify({"error": "no valid frames found in video"}), 422

    # apply max_frames cap
    if max_frames > 0:
        summary["valid_landmarks"]   = summary["valid_landmarks"][:max_frames]
        summary["valid_image_paths"] = summary["valid_image_paths"][:max_frames]
        summary["valid_frames"]      = len(summary["valid_landmarks"])

    # 2) Translate each frame landmarks → NAO angles
    frames = []
    for landmarks in summary["valid_landmarks"]:
        try:
            result = translate_arms(landmarks)
        except Exception as e:
            return jsonify({"error": "failed to translate landmarks", "detail": str(e)}), 500
        frames.append({
            "keypoints": landmarks,
            "nao_angles": result["angles"],
        })

    # 3) Save exercise in exerciseconfigservice
    try:
        config = call_exercise_create(
            name=name,
            frames=frames,
            pose_engine="mediapipe",
            media_bytes=video_bytes,
            media_ext=ext,
        )
    except requests.RequestException as e:
        return jsonify({"error": "failed to save exercise", "detail": str(e)}), 502

    # 4) Upload frame images to exerciseconfigservice
    exercise_id = config["id"]
    for frame_index, img_path in enumerate(summary["valid_image_paths"]):
        try:
            with open(img_path, "rb") as img_file:
                requests.post(
                    f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/frame/{frame_index}/image",
                    files={"image": ("frame.png", img_file, "image/png")},
                    timeout=10,
                )
        except Exception:
            pass  # images are best-effort, don't fail the whole request

    return jsonify(config), 201


@app.route("/arms/from_video", methods=["POST"])
def arms_from_video():
    """
    Accept a video, split into frames via pose_from_video, filter incomplete
    frames, send each valid pose to NAO, and save debug frame images.

    Request:
      multipart/form-data
        video: file
      optional form fields:
        fps: int (default 1)
        seconds: int (default -1, process full video)

    Response:
      200 JSON summary with counts and debug paths
      4xx/5xx JSON on error
    """
    if "video" not in request.files:
        return jsonify({"error": "video file is required (multipart/form-data, field 'video')"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    # Optional controls
    try:
        fps = int(request.form.get("fps", "1"))
    except ValueError:
        return jsonify({"error": "fps must be an integer"}), 400

    try:
        seconds = int(request.form.get("seconds", "-1"))
    except ValueError:
        return jsonify({"error": "seconds must be an integer"}), 400

    # Read video bytes (not necessarily saving the original file)
    try:
        video_bytes = file.read()
    except Exception as e:
        return jsonify({"error": "failed to read uploaded video", "detail": str(e)}), 500

    # Each upload gets its own debug frame folder
    upload_id = uuid.uuid4().hex
    output_dir = os.path.join(VIDEO_FRAMES_ROOT, upload_id)
    os.makedirs(output_dir, exist_ok=True)

    # 1) Process video via pose_from_video → frames + debug images
    try:
        summary = process_video_bytes(
            video_bytes=video_bytes,
            output_dir=output_dir,
            number_frames_per_sec=fps,
            number_seconds_to_process=seconds,
            attach_visualization=True,
        )
    except requests.RequestException as e:
        return jsonify({
            "error": "failed to call pose_from_video service",
            "detail": str(e),
        }), 502
    except Exception as e:
        return jsonify({
            "error": "failed to process video",
            "detail": str(e),
        }), 500

    if summary["valid_frames"] == 0:
        return jsonify({
            "error": "no valid frames with complete landmarks in video",
            "total_frames": summary["total_frames"],
            "output_dir": output_dir,
            "invalid_image_paths": summary["invalid_image_paths"],
        }), 422

    # 2) For each valid frame, translate landmarks -> NAO angles and send to NAO
    nao_results = []
    for idx, landmarks in enumerate(summary["valid_landmarks"]):
        try:
            result = translate_arms(landmarks)
            angles = result["angles"]
        except Exception as e:
            return jsonify({
                "error": "failed to translate landmarks to NAO angles for a frame",
                "detail": str(e),
                "frame_index_in_valid_list": idx,
            }), 500

        # Send to NAO
        try:
            nao_response = call_nao_set_pose(angles)
        except requests.RequestException as e:
            return jsonify({
                "error": "failed to send pose to NAO for a frame",
                "detail": str(e),
                "frame_index_in_valid_list": idx,
            }), 502

        # Collect a minimal per-frame summary (avoid huge payload)
        nao_results.append({
            "frame_valid_index": idx,
            "nao_response": nao_response,
        })

    # 3) Final summary
    return jsonify({
        "upload_id": upload_id,
        "output_dir": output_dir,
        "total_frames": summary["total_frames"],
        "valid_frames": summary["valid_frames"],
        "invalid_frames": summary["invalid_frames"],
        "valid_image_paths": summary["valid_image_paths"],
        "invalid_image_paths": summary["invalid_image_paths"],
        "landmarks_valid_json": summary["landmarks_valid_json"],
        "landmarks_all_json": summary["landmarks_all_json"],
        "nao_results": nao_results,
    })


# =========================
# EXERCISE CRUD PROXIES
# =========================

@app.route("/exercise/list", methods=["GET"])
def exercise_list():
    resp = requests.get(f"{EXERCISE_CONFIG_URL}/exercise/list", timeout=10)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>", methods=["GET"])
def exercise_get(exercise_id):
    resp = requests.get(f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}", timeout=10)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>", methods=["DELETE"])
def exercise_delete(exercise_id):
    resp = requests.delete(f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}", timeout=10)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>/config", methods=["PUT"])
def exercise_patch_config(exercise_id):
    resp = requests.put(
        f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/config",
        json=request.get_json(silent=True) or {},
        timeout=10,
    )
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>/frames", methods=["GET"])
def exercise_get_frames(exercise_id):
    resp = requests.get(f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/frames", timeout=10)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>/sequence", methods=["PUT"])
def exercise_patch_sequence(exercise_id):
    resp = requests.put(
        f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/sequence",
        json=request.get_json(silent=True) or {},
        timeout=10,
    )
    return jsonify(resp.json()), resp.status_code


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=False)
