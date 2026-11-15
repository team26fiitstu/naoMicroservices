"""
Integration tests for nao_pose_service.py routes.
External services (skeletonfinderapi, exerciseconfigservice, naorobotapi)
are mocked with unittest.mock so no network calls are made.
"""

import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import nao_pose_service as svc

# ---------------------------------------------------------------------------
# Test assets — real files from project root
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
IMAGE_PATH = os.path.join(PROJECT_ROOT, "frame_5.jpg")
VIDEO_PATH = os.path.join(PROJECT_ROOT, "video_2.mp4")

assert os.path.exists(IMAGE_PATH), f"Test image not found: {IMAGE_PATH}"
assert os.path.exists(VIDEO_PATH), f"Test video not found: {VIDEO_PATH}"

# Flask test client
app = svc.app
app.config["TESTING"] = True
client = app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_LANDMARKS = {
    "Left shoulder":  {"x": 0.60, "y": 0.40, "z": -0.30},
    "Right shoulder": {"x": 0.42, "y": 0.36, "z": -0.31},
    "Left elbow":     {"x": 0.62, "y": 0.53, "z": -0.24},
    "Right elbow":    {"x": 0.36, "y": 0.26, "z": -0.41},
    "Left wrist":     {"x": 0.61, "y": 0.63, "z": -0.28},
    "Right wrist":    {"x": 0.32, "y": 0.11, "z": -0.43},
}

SAMPLE_EXERCISE_CONFIG = {
    "id": "abc12345",
    "name": "Test Exercise",
    "created_at": "2026-03-27T10:00:00",
    "pose_engine": "mediapipe",
    "repetitions": 2,
    "frame_sequence": [0, 1],
}

SAMPLE_FRAMES = [
    {"frame_index": 0, "keypoints": SAMPLE_LANDMARKS, "nao_angles": [0.1] * 22},
    {"frame_index": 1, "keypoints": SAMPLE_LANDMARKS, "nao_angles": [0.2] * 22},
]


def mock_response(data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = data
    m.raise_for_status = MagicMock()
    return m


# ---------------------------------------------------------------------------
# GET /test
# ---------------------------------------------------------------------------

def test_health():
    resp = client.get("/test")
    assert resp.status_code == 200
    assert b"running" in resp.data


# ---------------------------------------------------------------------------
# POST /arms/from_landmarks
# ---------------------------------------------------------------------------

def test_from_landmarks_valid():
    resp = client.post("/arms/from_landmarks",
                       json=SAMPLE_LANDMARKS,
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "nao_angles" in data
    assert "keypoints" in data
    assert "joint_values" in data
    assert len(data["nao_angles"]) == 22


def test_from_landmarks_missing_joint():
    bad = dict(SAMPLE_LANDMARKS)
    del bad["Left elbow"]
    resp = client.post("/arms/from_landmarks", json=bad)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_from_landmarks_no_body():
    resp = client.post("/arms/from_landmarks",
                       data="not json",
                       content_type="text/plain")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /exercise/from_image
# ---------------------------------------------------------------------------

def test_exercise_from_image_success():
    skeleton_resp = mock_response(SAMPLE_LANDMARKS)
    exconf_resp = mock_response(SAMPLE_EXERCISE_CONFIG, 201)

    with patch("nao_pose_service.requests.post") as mock_post:
        mock_post.side_effect = [skeleton_resp, exconf_resp]

        with open(IMAGE_PATH, "rb") as f:
            resp = client.post("/exercise/from_image",
                               data={"name": "Test Exercise",
                                     "image": (f, "frame_5.jpg")},
                               content_type="multipart/form-data")

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == "abc12345"


def test_exercise_from_image_no_file():
    resp = client.post("/exercise/from_image",
                       data={"name": "Test"},
                       content_type="multipart/form-data")
    assert resp.status_code == 400


def test_exercise_from_image_incomplete_pose():
    """Skeleton returns landmarks missing required joints → 422."""
    bad_landmarks = {"Nose": {"x": 0.5, "y": 0.5, "z": 0.0}}
    skeleton_resp = mock_response(bad_landmarks)

    with patch("nao_pose_service.requests.post", return_value=skeleton_resp):
        with open(IMAGE_PATH, "rb") as f:
            resp = client.post("/exercise/from_image",
                               data={"name": "Test",
                                     "image": (f, "frame_5.jpg")},
                               content_type="multipart/form-data")

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /exercise/from_video
# ---------------------------------------------------------------------------

def test_exercise_from_video_success():
    valid_landmarks_list = [SAMPLE_LANDMARKS, SAMPLE_LANDMARKS]
    video_summary = {
        "total_frames": 2,
        "valid_frames": 2,
        "invalid_frames": 0,
        "valid_landmarks": valid_landmarks_list,
        "valid_image_paths": [],
        "invalid_image_paths": [],
        "landmarks_valid_json": "/tmp/x.json",
        "landmarks_all_json": "/tmp/y.json",
    }
    exconf_resp = mock_response(SAMPLE_EXERCISE_CONFIG, 201)

    with patch("nao_pose_service.process_video_bytes", return_value=video_summary), \
         patch("nao_pose_service.requests.post", return_value=exconf_resp):
        with open(VIDEO_PATH, "rb") as f:
            resp = client.post("/exercise/from_video",
                               data={"name": "Video Exercise",
                                     "fps": "2",
                                     "seconds": "5",
                                     "video": (f, "video_2.mp4")},
                               content_type="multipart/form-data")

    assert resp.status_code == 201
    assert resp.get_json()["id"] == "abc12345"


def test_exercise_from_video_no_valid_frames():
    video_summary = {
        "total_frames": 3,
        "valid_frames": 0,
        "invalid_frames": 3,
        "valid_landmarks": [],
        "valid_image_paths": [],
        "invalid_image_paths": [],
        "landmarks_valid_json": "/tmp/x.json",
        "landmarks_all_json": "/tmp/y.json",
    }

    with patch("nao_pose_service.process_video_bytes", return_value=video_summary):
        with open(VIDEO_PATH, "rb") as f:
            resp = client.post("/exercise/from_video",
                               data={"name": "Bad Video",
                                     "video": (f, "video_2.mp4")},
                               content_type="multipart/form-data")

    assert resp.status_code == 422


def test_exercise_from_video_no_file():
    resp = client.post("/exercise/from_video",
                       data={"name": "Test"},
                       content_type="multipart/form-data")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /exercise/<id>/run
# ---------------------------------------------------------------------------

def test_exercise_run_success():
    frames_resp = mock_response(SAMPLE_FRAMES)
    config_resp = mock_response(SAMPLE_EXERCISE_CONFIG)
    nao_resp = mock_response({"status": "ok"})

    with patch("nao_pose_service.requests.get") as mock_get, \
         patch("nao_pose_service.requests.post", return_value=nao_resp):
        mock_get.side_effect = [frames_resp, config_resp]

        resp = client.post("/exercise/abc12345/run",
                           json={},
                           content_type="application/json")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["exercise_id"] == "abc12345"
    # 2 frames × 2 repetitions = 4 total poses
    assert data["total_poses_sent"] == 4
    assert data["repetitions"] == 2
    assert data["frames_per_rep"] == 2


def test_exercise_run_repetitions_override():
    """Repetitions in request body overrides config value."""
    frames_resp = mock_response(SAMPLE_FRAMES)
    nao_resp = mock_response({"status": "ok"})

    with patch("nao_pose_service.requests.get", return_value=frames_resp), \
         patch("nao_pose_service.requests.post", return_value=nao_resp):

        resp = client.post("/exercise/abc12345/run",
                           json={"repetitions": 1},
                           content_type="application/json")

    assert resp.status_code == 200
    data = resp.get_json()
    # 2 frames × 1 rep = 2
    assert data["total_poses_sent"] == 2
    assert data["repetitions"] == 1


def test_exercise_run_not_found():
    not_found = mock_response({"error": "not found"}, 404)

    with patch("nao_pose_service.requests.get", return_value=not_found):
        resp = client.post("/exercise/nonexistent/run", json={})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Proxy routes
# ---------------------------------------------------------------------------

def test_proxy_exercise_list():
    exconf_resp = mock_response([SAMPLE_EXERCISE_CONFIG])

    with patch("nao_pose_service.requests.get", return_value=exconf_resp):
        resp = client.get("/exercise/list")

    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["id"] == "abc12345"


def test_proxy_exercise_get():
    exconf_resp = mock_response(SAMPLE_EXERCISE_CONFIG)

    with patch("nao_pose_service.requests.get", return_value=exconf_resp):
        resp = client.get("/exercise/abc12345")

    assert resp.status_code == 200
    assert resp.get_json()["id"] == "abc12345"


def test_proxy_exercise_delete():
    exconf_resp = mock_response({"deleted": "abc12345"})

    with patch("nao_pose_service.requests.delete", return_value=exconf_resp):
        resp = client.delete("/exercise/abc12345")

    assert resp.status_code == 200
    assert resp.get_json()["deleted"] == "abc12345"


def test_proxy_exercise_get_frames():
    exconf_resp = mock_response(SAMPLE_FRAMES)

    with patch("nao_pose_service.requests.get", return_value=exconf_resp):
        resp = client.get("/exercise/abc12345/frames")

    assert resp.status_code == 200
    assert len(resp.get_json()) == 2
