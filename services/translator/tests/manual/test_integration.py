"""
Integration tests — real HTTP calls against running services.

Requires all services to be up:
    docker-compose -f docker-compose.dev.yml up -d naorobotapi skeletonfinderapi translatorapi exercise-config-service

NAO robot does NOT need to be connected — run endpoint will report
per-frame errors but the test checks the flow, not the robot response.
"""

import requests
import os
import pytest

TRANSLATOR = "http://localhost:7000"

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
IMAGE_PATH = os.path.join(PROJECT_ROOT, "frame_5.jpg")
VIDEO_PATH = os.path.join(PROJECT_ROOT, "video_2.mp4")

created_ids = []  # track for cleanup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cleanup():
    for ex_id in created_ids:
        try:
            requests.delete(f"{TRANSLATOR}/exercise/{ex_id}", timeout=5)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

def test_translator_health():
    resp = requests.get(f"{TRANSLATOR}/test", timeout=5)
    assert resp.status_code == 200, "translatorapi is not running"


def test_exercise_list_reachable():
    resp = requests.get(f"{TRANSLATOR}/exercise/list", timeout=5)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Create exercise from image
# ---------------------------------------------------------------------------

def test_create_exercise_from_image():
    with open(IMAGE_PATH, "rb") as f:
        resp = requests.post(
            f"{TRANSLATOR}/exercise/from_image",
            files={"image": ("frame_5.jpg", f, "image/jpeg")},
            data={"name": "Integration Test Image"},
            timeout=30,
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "id" in data
    assert data["name"] == "Integration Test Image"
    assert data["pose_engine"] == "mediapipe"
    assert len(data["frame_sequence"]) == 1  # single image = 1 frame
    created_ids.append(data["id"])


# ---------------------------------------------------------------------------
# Create exercise from video
# ---------------------------------------------------------------------------

def test_create_exercise_from_video():
    with open(VIDEO_PATH, "rb") as f:
        resp = requests.post(
            f"{TRANSLATOR}/exercise/from_video",
            files={"video": ("video_2.mp4", f, "video/mp4")},
            data={"name": "Integration Test Video", "fps": "2", "seconds": "5"},
            timeout=120,
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "id" in data
    assert data["name"] == "Integration Test Video"
    assert len(data["frame_sequence"]) > 0
    created_ids.append(data["id"])


# ---------------------------------------------------------------------------
# List — both exercises appear
# ---------------------------------------------------------------------------

def test_list_contains_created_exercises():
    resp = requests.get(f"{TRANSLATOR}/exercise/list", timeout=5)
    assert resp.status_code == 200
    ids = [ex["id"] for ex in resp.json()]
    for ex_id in created_ids:
        assert ex_id in ids, f"Exercise {ex_id} missing from list"


# ---------------------------------------------------------------------------
# Get exercise detail
# ---------------------------------------------------------------------------

def test_get_exercise_detail():
    assert created_ids, "No exercises created yet"
    ex_id = created_ids[0]
    resp = requests.get(f"{TRANSLATOR}/exercise/{ex_id}", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["id"] == ex_id


# ---------------------------------------------------------------------------
# Get frames
# ---------------------------------------------------------------------------

def test_get_exercise_frames():
    assert created_ids, "No exercises created yet"
    ex_id = created_ids[0]
    resp = requests.get(f"{TRANSLATOR}/exercise/{ex_id}/frames", timeout=5)
    assert resp.status_code == 200
    frames = resp.json()
    assert isinstance(frames, list)
    assert len(frames) > 0
    assert "nao_angles" in frames[0]
    assert "keypoints" in frames[0]
    assert len(frames[0]["nao_angles"]) == 22


# ---------------------------------------------------------------------------
# Run exercise (NAO may not be connected — check flow not robot)
# ---------------------------------------------------------------------------

def _run_and_assert(ex_id, repetitions=1):
    print(f"\n  Exercise '{ex_id}' received from exerciseconfigservice")

    frames_resp = requests.get(f"{TRANSLATOR}/exercise/{ex_id}/frames", timeout=5)
    frames = frames_resp.json()
    sequence = [f["frame_index"] for f in frames]
    print(f"  Frame sequence: {sequence}")
    print(f"  Sending {len(frames)} frame(s) × {repetitions} rep(s) to NAO robot...")

    resp = requests.post(
        f"{TRANSLATOR}/exercise/{ex_id}/run",
        json={"repetitions": repetitions},
        timeout=300,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    for r in data["results"]:
        print(f"    rep {r['rep']} frame {r['frame_index']} → {r['status']}")

    print(f"  Done. {data['total_poses_sent']} pose(s) sent")

    assert data["exercise_id"] == ex_id
    assert data["repetitions"] == repetitions
    assert data["frames_per_rep"] == len(frames)
    assert data["total_poses_sent"] == len(frames) * repetitions
    assert len(data["results"]) == data["total_poses_sent"]


def test_run_exercise():
    assert created_ids, "No exercises created yet"
    ex_id = created_ids[0]  # image exercise — 1 frame
    _run_and_assert(ex_id, repetitions=1)


def test_run_video_exercise():
    assert len(created_ids) >= 2, "Video exercise not created yet"
    ex_id = created_ids[1]  # video exercise — multiple frames
    _run_and_assert(ex_id, repetitions=1)


# ---------------------------------------------------------------------------
# Update config
# ---------------------------------------------------------------------------

def test_update_exercise_config():
    assert created_ids, "No exercises created yet"
    ex_id = created_ids[0]
    resp = requests.put(
        f"{TRANSLATOR}/exercise/{ex_id}/config",
        json={"name": "Renamed Exercise", "repetitions": 3},
        timeout=5,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Renamed Exercise"
    assert data["repetitions"] == 3


# ---------------------------------------------------------------------------
# Delete exercises (cleanup)
# ---------------------------------------------------------------------------

def test_delete_created_exercises():
    for ex_id in list(created_ids):
        resp = requests.delete(f"{TRANSLATOR}/exercise/{ex_id}", timeout=5)
        assert resp.status_code == 200
        created_ids.remove(ex_id)

    # verify gone
    resp = requests.get(f"{TRANSLATOR}/exercise/list", timeout=5)
    ids = [ex["id"] for ex in resp.json()]
    for ex_id in created_ids:
        assert ex_id not in ids
