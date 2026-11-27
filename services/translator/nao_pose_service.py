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
from dotenv import load_dotenv

# Load only the repository root file; container environment takes precedence.
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))

import math
import uuid
import json
import tempfile
import re
import threading

from flask import Flask, request, jsonify
import requests

from arms_translator import translate_arms
from video_pose_processor import process_video_bytes
from flask_cors import CORS
from runtime_config import service_host
from http_retry import request_with_retries

POSE_API_URL = "http://%s:6001/media_pipe_pose/pose_from_image" % service_host("skeletonfinderapi")
SET_POSE_URL = "http://%s:5000/setting_pose/setPose" % service_host("naorobotapi")
VOICE_LINES_URL = "http://%s:5000/voiceLines/applyVoiceLine" % service_host("naorobotapi")
ROBOT_RESERVATION_URL = "http://%s:5000/control/reservation" % service_host("naorobotapi")
EXERCISE_CONFIG_URL = "http://%s:7001" % service_host("exercise-config-service")
_robot_run_context = threading.local()

# name of unnamed exercise, Slovak UI
DEFAULT_EXERCISE_NAME = "Nepomenované cvičenie"

# Host directory mounted into pose container as /images
POSE_HOST_ROOT = os.path.abspath(os.environ.get("POSE_IMAGE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "images")))
POSE_CONT_ROOT = os.environ.get("POSE_SERVICE_IMAGE_DIR", POSE_HOST_ROOT)

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
    resp = request_with_retries("GET", POSE_API_URL, params=params, timeout=15)
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


def call_exercise_create(name, frames, pose_engine="mediapipe", media_bytes=None, media_ext=".mp4",
                         video_range=None):
    """
    POST to exerciseconfigservice /exercise/create.
    Sends frames and optional video range as JSON form fields, optionally attaches media file.
    Returns the created exercise config dict.
    """
    data = {
        "name": (None, name),
        "pose_engine": (None, pose_engine),
        "frames": (None, json.dumps(frames), "application/json"),
    }
    if video_range is not None:
        data["video_range"] = (None, json.dumps(video_range), "application/json")
    if media_bytes is not None:
        ext = media_ext if media_ext.startswith(".") else f".{media_ext}"
        data["media"] = (f"original{ext}", media_bytes, "application/octet-stream")

    resp = request_with_retries("POST", f"{EXERCISE_CONFIG_URL}/exercise/create", files=data, timeout=30,
                              idempotent=False)
    resp.raise_for_status()
    return resp.json()


def call_nao_set_pose(angles):
    """
    Call NAO pose endpoint with the given angles.
    """
    payload = {"angles": angles}
    token = getattr(_robot_run_context, "token", None)
    headers = {"X-Robot-Run-Token": token} if token else None
    resp = request_with_retries("POST", SET_POSE_URL, json=payload, headers=headers, timeout=15,
                              idempotent=False)
    resp.raise_for_status()
    return resp.json()


def call_nao_voice_lines(voice_lines_configs):
    """
    Call NAO to say voice line.
    """
    payload = {"voice_lines": voice_lines_configs}
    token = getattr(_robot_run_context, "token", None)
    headers = {"X-Robot-Run-Token": token} if token else None
    resp = request_with_retries("POST", VOICE_LINES_URL, json=payload, headers=headers, timeout=15,
                              idempotent=False,
                              max_attempts=1)  # a repeated voice line is audible: never retry
    resp.raise_for_status()
    return resp.json()


def reserve_robot_for_run(run_id):
    try:
        resp = request_with_retries("POST", ROBOT_RESERVATION_URL,
                                    json={"token": run_id}, timeout=5,
                                    idempotent=True, max_attempts=2)
        if resp.status_code == 409:
            return jsonify({"error": "robot is reserved by another run"}), 409
        resp.raise_for_status()
        if resp.json().get("success") is not True:
            raise ValueError("robot did not confirm reservation")
    except (requests.RequestException, ValueError, AttributeError) as exc:
        return jsonify({"error": "failed to reserve robot", "detail": str(exc)}), 502
    return None


def release_robot_reservation(run_id):
    try:
        resp = request_with_retries("DELETE", ROBOT_RESERVATION_URL,
                                    json={"token": run_id}, timeout=5,
                                    idempotent=True, max_attempts=2)
        resp.raise_for_status()
    except requests.RequestException:
        app.logger.exception("failed to release robot reservation for run %s", run_id)
        return False
    return True


def fetch_exercise(exercise_id, repetitions_override=None):
    """Return stored playback frames and repetition count, or an HTTP error tuple."""
    try:
        resp = request_with_retries("GET", f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/frames", timeout=10)
        if resp.status_code == 404:
            return None, (jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404)
        resp.raise_for_status()
        frames = resp.json()
    except (requests.RequestException, ValueError) as exc:
        return None, (jsonify({"error": "failed to fetch frames", "detail": str(exc)}), 502)
    if not isinstance(frames, list):
        return None, (jsonify({"error": "invalid exercise frames"}), 502)
    if not frames:
        return None, (jsonify({"error": "exercise has no frames"}), 422)
    if any(not isinstance(frame, dict) for frame in frames):
        return None, (jsonify({"error": "invalid exercise frames"}), 502)
    if not any(frame.get("voice_lines") or frame.get("nao_angles") for frame in frames):
        return None, (jsonify({"error": "exercise has no playable content"}), 422)

    repetitions = repetitions_override
    if repetitions is None:
        try:
            resp = request_with_retries("GET", f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}", timeout=10)
            if resp.status_code == 404:
                return None, (jsonify({"error": f"Exercise '{exercise_id}' not found"}), 404)
            resp.raise_for_status()
            repetitions = resp.json().get("repetitions", 1)
        except (requests.RequestException, ValueError, AttributeError) as exc:
            return None, (jsonify({"error": "failed to fetch exercise config", "detail": str(exc)}), 502)
    try:
        repetitions = int(repetitions)
        if repetitions < 1:
            raise ValueError
    except (ValueError, TypeError):
        return None, (jsonify({"error": "repetitions must be a positive integer"}), 400)
    return (frames, repetitions), None


def play_exercise(exercise_id, repetitions_override=None, stop_on_error=False,
                  legacy_results=False, cancelled=None):
    fetched, error = fetch_exercise(exercise_id, repetitions_override)
    if error:
        return None, error
    frames, repetitions = fetched
    results = []
    for rep in range(repetitions):
        for frame in frames:
            if cancelled and cancelled():
                return playback_result(exercise_id, repetitions, frames, results), None
            for kind, payload, sender in (
                ("voice", frame.get("voice_lines"), call_nao_voice_lines),
                ("pose", frame.get("nao_angles", []), call_nao_set_pose),
            ):
                if not payload:
                    continue
                item = {"rep": rep, "type": kind, "frame_index": frame.get("frame_index")}
                try:
                    robot_result = sender(payload)
                    if not isinstance(robot_result, dict) or robot_result.get("success") is not True:
                        raise RuntimeError("robot did not confirm success")
                    item["status"] = "ok"
                    if legacy_results and kind == "voice":
                        # Keep the historical /exercise/<id>/run result shape.
                        item["type"] = "pose"
                except (requests.RequestException, RuntimeError) as exc:
                    item.update(status="error", detail=str(exc))
                results.append(item)
                if stop_on_error and item["status"] == "error":
                    return playback_result(exercise_id, repetitions, frames, results), None
    return playback_result(exercise_id, repetitions, frames, results), None


def playback_result(exercise_id, repetitions, frames, results):
    return {"exercise_id": exercise_id, "repetitions": repetitions,
            "frames_per_rep": len(frames), "total_poses_sent": len(results), "results": results}
    

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
        name:  string (default DEFAULT_EXERCISE_NAME)

    Response:
        201 JSON: exercise config
    """
    if "image" not in request.files:
        return jsonify({"error": "image file is required (field 'image')"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    name = request.form.get("name", DEFAULT_EXERCISE_NAME)
    ext = os.path.splitext(file.filename)[1] or ".jpg"

    try:
        image_bytes = file.read()
    except Exception as e:
        return jsonify({"error": "failed to read image", "detail": str(e)}), 500

    # 1) Get landmarks from skeletonfinderapi via base64 POST
    import base64
    try:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        resp = request_with_retries(
            "POST",
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
    with _robot_playback_lock:
        result, error = play_exercise(exercise_id, data.get("repetitions"),
                                      legacy_results=True)
    return error if error else (jsonify(result), 200)


# A translator process controls one robot and therefore one active run.
_runs = {}  # run_id -> run; only recent stopped runs remain queryable
_stopped_run_ids = []
MAX_STOPPED_RUNS = 50
_current_run_id = None
_starting = False
_run_registry_lock = threading.Lock()
_robot_playback_lock = threading.Lock()
_choreography_id_re = re.compile(r"^[0-9a-f]{8}$")


def _snapshot(run):
    state_id = run["state_id"]
    return {"run_id": run["run_id"], "choreography_id": run["choreography_id"],
            "state_id": state_id, "status": run["status"],
            "outgoing_transitions": [dict(t) for t in run["graph"]["transitions"]
                                     if t["from"] == state_id],
            "playback": run["playback"], "error": run["error"]}


def _retain_stopped_run(run):
    """Keep a bounded history for GET /run/<run_id> after completion."""
    if run["retained"]:
        return
    run["retained"] = True
    _stopped_run_ids.append(run["run_id"])
    if len(_stopped_run_ids) > MAX_STOPPED_RUNS:
        _runs.pop(_stopped_run_ids.pop(0), None)


def _take_reservation_release(run):
    if run["reservation_released"]:
        return None
    run["reservation_released"] = True
    return run["run_id"]


def _renew_run_reservation(run):
    # Stop must not release the lease before an in-flight renewal completes.
    with run["reservation_lock"]:
        if run["stop_event"].is_set():
            return None
        return reserve_robot_for_run(run["run_id"])


def _release_run_reservation(run):
    with run["reservation_lock"]:
        return release_robot_reservation(run["run_id"])


def _renew_robot_reservation(run):
    global _current_run_id
    with app.app_context():
        while not run["stop_event"].wait(20):
            failure = _renew_run_reservation(run)
            if failure is None:
                continue
            token_to_release = None
            with _run_registry_lock:
                if run["status"] == "stopped":
                    return
                run["error"] = "robot reservation was lost"
                run["stop_event"].set()
                run["status"] = "stopped"
                if run["worker_done"].is_set():
                    if _current_run_id == run["run_id"]:
                        _current_run_id = None
                    _retain_stopped_run(run)
                    token_to_release = _take_reservation_release(run)
            if token_to_release:
                released = _release_run_reservation(run)
                if not released:
                    with _run_registry_lock:
                        run["error"] += "; failed to release robot reservation"
            return


def _load_graph(choreography_id):
    try:
        resp = request_with_retries("GET", f"{EXERCISE_CONFIG_URL}/choreography/{choreography_id}", timeout=10)
        if resp.status_code == 404:
            return None, (jsonify({"error": f"Choreography '{choreography_id}' not found"}), 404)
        resp.raise_for_status()
        graph = resp.json()
    except (requests.RequestException, ValueError) as exc:
        return None, (jsonify({"error": "failed to fetch choreography", "detail": str(exc)}), 502)
    if not isinstance(graph, dict) or graph.get("schema_version") != 1 or graph.get("id") != choreography_id:
        return None, (jsonify({"error": "invalid choreography document"}), 502)
    states = graph.get("states")
    transitions = graph.get("transitions")
    if not isinstance(states, list) or not isinstance(transitions, list):
        return None, (jsonify({"error": "invalid choreography document"}), 502)
    state_ids = [state.get("state_id") for state in states if isinstance(state, dict)]
    if len(state_ids) != len(states) or any(
        not isinstance(state_id, str) or not _choreography_id_re.fullmatch(state_id)
        for state_id in state_ids
    ):
        return None, (jsonify({"error": "invalid choreography document"}), 502)
    ids = set(state_ids)
    transition_ids = [t.get("id") for t in transitions if isinstance(t, dict)]
    initial_state = graph.get("initial_state")
    if (len(ids) != len(states)
            or not isinstance(initial_state, str) or initial_state not in ids
            or len(transition_ids) != len(transitions)
            or any(not isinstance(tid, str) or not tid for tid in transition_ids)
            or len(set(transition_ids)) != len(transitions)
            or any(not isinstance(t.get("from"), str) or t["from"] not in ids
                   or not isinstance(t.get("to"), str) or t["to"] not in ids
                   for t in transitions)):
        return None, (jsonify({"error": "invalid choreography document"}), 502)
    return graph, None


def _perform_state(run, target, starting):
    """Complete one performance and publish its result."""
    with app.app_context():
        _perform_state_in_context(run, target, starting)


def _perform_state_in_context(run, target, starting):
    global _current_run_id
    try:
        with _robot_playback_lock:
            _robot_run_context.token = run["run_id"]
            try:
                result, failure = play_exercise(target, stop_on_error=True,
                                                cancelled=run["stop_event"].is_set)
            finally:
                del _robot_run_context.token
    except Exception:
        app.logger.exception("choreography playback failed for run %s", run["run_id"])
        result, failure = None, (jsonify({"error": "unexpected playback failure"}), 502)
    token_to_release = None
    with _run_registry_lock:
        run["playback"] = result
        if failure:
            playback_error = failure[0].get_json()["error"]
        elif result is not None and any(item["status"] == "error" for item in result["results"]):
            playback_error = "robot playback failed; some commands may have completed"
        else:
            playback_error = None
        if run["error"]:
            if playback_error:
                run["error"] += "; " + playback_error
        else:
            run["error"] = playback_error
        if run["error"] and not starting:
            run["state_id"] = run["source_state_id"]
        if run["stop_event"].is_set():
            run["status"] = "stopped"
        elif run["error"]:
            run["status"] = "stopped" if starting else "waiting"
        else:
            run["status"] = "waiting"
        run["source_state_id"] = None
        if run["status"] == "stopped":
            run["stop_event"].set()
            token_to_release = _take_reservation_release(run)
        else:
            run["worker_done"].set()
    if token_to_release:
        released = _release_run_reservation(run)
    if token_to_release:
        with _run_registry_lock:
            if not released:
                release_error = "failed to release robot reservation; it will expire automatically"
                run["error"] = run["error"] + "; " + release_error if run["error"] else release_error
            run["worker_done"].set()
            if _current_run_id == run["run_id"]:
                _current_run_id = None
            _retain_stopped_run(run)


def _start_performance(run, target, starting=False):
    previous = (run["source_state_id"], run["state_id"], run["status"],
                run["error"], run["worker_done"].is_set())
    run["source_state_id"] = None if starting else run["state_id"]
    run["state_id"] = target
    run["status"] = "performing"
    run["error"] = None
    run["worker_done"].clear()
    try:
        worker = threading.Thread(target=_perform_state, args=(run, target, starting), daemon=True)
        worker.start()
    except RuntimeError:
        run["source_state_id"], run["state_id"], run["status"], run["error"], was_done = previous
        if was_done:
            run["worker_done"].set()
        raise


@app.route("/choreography/<choreography_id>/run", methods=["POST"])
def start_choreography_run(choreography_id):
    global _current_run_id, _starting
    if not _choreography_id_re.fullmatch(choreography_id):
        return jsonify({"error": "choreography_id must be an 8-character lowercase hex ID"}), 400
    with _run_registry_lock:
        if _current_run_id is not None or _starting:
            return jsonify({"error": "another choreography run is active"}), 409
        _starting = True
    try:
        graph, failure = _load_graph(choreography_id)
        if failure:
            return failure
        run_id = uuid.uuid4().hex
        failure = reserve_robot_for_run(run_id)
        if failure:
            if failure[1] == 502:
                # A lost POST response does not prove the robot rejected the lease.
                # DELETE retires this token even when the POST arrives later.
                if not release_robot_reservation(run_id):
                    app.logger.error("could not retire uncertain reservation for run %s", run_id)
            return failure
        worker_error = None
        with _run_registry_lock:
            run = {"run_id": run_id, "choreography_id": choreography_id,
                   "graph": graph, "state_id": graph["initial_state"],
                   "status": "performing", "stop_event": threading.Event(),
                   "worker_done": threading.Event(), "source_state_id": None,
                   "playback": None, "error": None, "retained": False,
                   "reservation_released": False,
                   "reservation_lock": threading.Lock()}
            _runs[run_id] = run
            _current_run_id = run_id
            try:
                _start_performance(run, graph["initial_state"], starting=True)
            except RuntimeError as exc:
                _runs.pop(run_id)
                _current_run_id = None
                worker_error = str(exc)
            else:
                try:
                    threading.Thread(target=_renew_robot_reservation, args=(run,), daemon=True).start()
                except RuntimeError as exc:
                    run["stop_event"].set()
                    run["status"] = "stopped"
                    run["error"] = "failed to start reservation monitor: " + str(exc)
                    return jsonify(_snapshot(run)), 503
                return jsonify(_snapshot(run)), 202
        released = release_robot_reservation(run_id)
        error = {"error": "failed to start playback worker", "detail": worker_error}
        if not released:
            error["cleanup_error"] = "robot reservation may remain until it expires"
        return jsonify(error), 503
    finally:
        with _run_registry_lock:
            _starting = False


@app.route("/run/current", methods=["GET"])
def current_choreography_run():
    with _run_registry_lock:
        if _current_run_id is None or _runs[_current_run_id]["status"] == "stopped":
            return jsonify({"error": "no active choreography run"}), 404
        return jsonify(_snapshot(_runs[_current_run_id])), 200


@app.route("/run/<run_id>", methods=["GET"])
def get_choreography_run(run_id):
    with _run_registry_lock:
        run = _runs.get(run_id)
        return (jsonify(_snapshot(run)), 200) if run else (jsonify({"error": "run not found"}), 404)


@app.route("/run/<run_id>/signal", methods=["POST"])
def signal_choreography_run(run_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("transition_id"), str) or not data["transition_id"]:
        return jsonify({"error": "JSON transition_id is required"}), 400
    with _run_registry_lock:
        run = _runs.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        if run["status"] != "waiting":
            return jsonify({"error": "run must be waiting for a signal"}), 409
        transition = next((t for t in run["graph"]["transitions"] if t["id"] == data["transition_id"]), None)
        if transition is None:
            return jsonify({"error": f"Transition '{data['transition_id']}' not found in this run"}), 409
        if transition["from"] != run["state_id"]:
            return jsonify({"error": "transition does not start at current state"}), 409
        try:
            _start_performance(run, transition["to"])
        except RuntimeError as exc:
            return jsonify({"error": "failed to start playback worker", "detail": str(exc)}), 503
        return jsonify(_snapshot(run)), 202


@app.route("/run/<run_id>/goto", methods=["POST"])
def goto_choreography_state(run_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("state_id"), str) or not data["state_id"]:
        return jsonify({"error": "JSON state_id is required"}), 400
    with _run_registry_lock:
        run = _runs.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        if run["status"] != "waiting":
            return jsonify({"error": "run must be waiting before goto"}), 409
        if data["state_id"] not in {s["state_id"] for s in run["graph"]["states"]}:
            return jsonify({"error": f"State '{data['state_id']}' not found"}), 404
        run["state_id"] = data["state_id"]
        run["playback"] = None
        run["error"] = None
        return jsonify(_snapshot(run)), 200


@app.route("/run/<run_id>/stop", methods=["POST"])
def stop_choreography_run(run_id):
    global _current_run_id
    token_to_release = None
    with _run_registry_lock:
        run = _runs.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        if run["status"] == "stopped":
            return jsonify({"error": "run already stopped"}), 409
        run["stop_event"].set()
        run["status"] = "stopped"
        # Keep the robot reserved until an in-flight command finishes.
        if run["worker_done"].is_set():
            _current_run_id = None
            _retain_stopped_run(run)
            token_to_release = _take_reservation_release(run)
    if token_to_release:
        released = _release_run_reservation(run)
        if not released:
            with _run_registry_lock:
                release_error = "failed to release robot reservation; it will expire automatically"
                run["error"] = run["error"] + "; " + release_error if run["error"] else release_error
    with _run_registry_lock:
        return jsonify(_snapshot(run)), 200


def parse_time_range(form):
    """Optional start/end form fields in seconds, end -1 means until end."""
    try:
        start = float(form.get("start", "0") or 0)
        end = float(form.get("end", "-1") or -1)
    except ValueError:
        raise ValueError("start and end must be numbers (seconds)") from None
    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("start and end must be finite numbers")
    if start < 0:
        raise ValueError("start must not be negative")
    if end != -1 and end <= start:
        raise ValueError("end must be greater than start")
    return start, end


@app.route("/exercise/from_video", methods=["POST"])
def exercise_from_video():
    """
    Full upload flow: video → skeleton → angles → save exercise.

    Request (multipart/form-data):
        video:   file
        name:    string (default DEFAULT_EXERCISE_NAME)
        fps:     int    (default 1)
        seconds: int    (default -1, full video)
        start:   float  (default 0, range start in seconds)
        end:     float  (default -1, range end, -1 = until end)

    Response:
        201 JSON: exercise config + frame_count
    """
    if "video" not in request.files:
        return jsonify({"error": "video file is required (field 'video')"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    name = request.form.get("name", DEFAULT_EXERCISE_NAME)

    try:
        fps = int(request.form.get("fps", "1"))
        seconds = int(request.form.get("seconds", "-1"))
        max_frames = int(request.form.get("max_frames", "-1"))
    except ValueError:
        return jsonify({"error": "fps, seconds, and max_frames must be integers"}), 400

    try:
        start_seconds, end_seconds = parse_time_range(request.form)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        video_bytes = file.read()
    except Exception as e:
        return jsonify({"error": "failed to read video", "detail": str(e)}), 500

    ext = os.path.splitext(file.filename)[1] or ".mp4"

    # Frames extracted from the upload are only needed long enough to be
    # translated and re-uploaded as part of the exercise; they are written to
    # a process-local temporary directory that is removed on every exit path
    # (success or error) so no copy is left outside the exercise's own
    # directory in exerciseConfigService.
    with tempfile.TemporaryDirectory(prefix="exercise-video-") as output_dir:
        # 1) Get landmarks from skeletonfinderapi
        try:
            summary = process_video_bytes(
                video_bytes=video_bytes,
                output_dir=output_dir,
                number_frames_per_sec=fps,
                number_seconds_to_process=seconds,
                attach_visualization=True,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
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
                # range selected in saved original video, seconds and max_frames may cut processing shorter
                video_range={"start": start_seconds, "end": None if end_seconds == -1 else end_seconds},
            )
        except requests.RequestException as e:
            return jsonify({"error": "failed to save exercise", "detail": str(e)}), 502

        # 4) Upload frame images to exerciseconfigservice (while the temporary
        #    frame directory still exists)
        exercise_id = config["id"]
        for frame_index, img_path in enumerate(summary["valid_image_paths"]):
            try:
                # Read the bytes once: an open file object is consumed by the first
                # attempt, so a retry would upload an empty image.
                with open(img_path, "rb") as img_file:
                    image_bytes = img_file.read()
                request_with_retries(
                    "POST",
                    f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/frame/{frame_index}/image",
                    files={"image": ("frame.png", image_bytes, "image/png")},
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

@app.errorhandler(requests.RequestException)
def handle_upstream_failure(e):
    """Uncaught upstream failure (e.g. exerciseconfigservice down) -> JSON 502, not an HTML 500."""
    return jsonify({"error": "upstream service unavailable", "detail": str(e)}), 502


@app.route("/exercise/list", methods=["GET"])
def exercise_list():
    resp = request_with_retries("GET", f"{EXERCISE_CONFIG_URL}/exercise/list", timeout=10)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>", methods=["GET"])
def exercise_get(exercise_id):
    resp = request_with_retries("GET", f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}", timeout=10)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>", methods=["DELETE"])
def exercise_delete(exercise_id):
    # A repeated DELETE after a lost response would return 404 for an exercise that
    # was in fact deleted, so only retry when the request was never sent.
    resp = request_with_retries("DELETE", f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}",
                                timeout=10, idempotent=False)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>/config", methods=["PUT"])
def exercise_patch_config(exercise_id):
    resp = request_with_retries(
        "PUT",
        f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/config",
        json=request.get_json(silent=True) or {},
        timeout=10,
    )
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>/frames", methods=["GET"])
def exercise_get_frames(exercise_id):
    resp = request_with_retries("GET", f"{EXERCISE_CONFIG_URL}/exercise/{exercise_id}/frames", timeout=10)
    return jsonify(resp.json()), resp.status_code


@app.route("/exercise/<exercise_id>/sequence", methods=["PUT"])
def exercise_patch_sequence(exercise_id):
    resp = request_with_retries(
        "PUT",
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
