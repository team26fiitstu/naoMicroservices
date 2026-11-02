"""
storage.py — all filesystem operations for ExerciseConfigService

Directory layout on disk (EXERCISES_DIR = /service/exercises in container):

  /service/exercises/
  ├── a3f9c1d2/                  ← exercise ID (8-char hex UUID)
  │   ├── config.json            ← exercise metadata + playback config
  │   ├── media/
  │   │   └── original.mp4       ← original uploaded file (video or image)
  │   └── frames/
  │       ├── frame_000.json     ← one file per frame
  │       ├── frame_001.json
  │       └── frame_002.json
  └── b7e2a091/
      ├── config.json
      ├── media/
      │   └── original.jpg
      └── frames/
          └── frame_000.json

config.json structure:
  {
    "id": "a3f9c1d2",
    "name": "Arm Wave",
    "created_at": "2026-03-16T12:00:00",
    "pose_engine": "mediapipe",        // or "yolo"
    "repetitions": 3,
    "frame_sequence": [0, 1, 2, 1, 0] // playback order — can repeat/reorder frames
  }

frame_NNN.json structure:
  {
    "frame_index": 0,
    "keypoints": {                     // raw skeleton from skeletonFinderAPI
      "left_shoulder": [x, y, z],
      "right_shoulder": [x, y, z],
      ...
    },
    "nao_angles": [                    // 8 floats, ready to send to naoRobotAPI
      LShoulderPitch,
      LShoulderRoll,
      LElbowRoll,
      LElbowYaw,
      RShoulderPitch,
      RShoulderRoll,
      RElbowRoll,
      RElbowYaw
    ]
  }
"""

import os
import json
import shutil
import uuid
from datetime import datetime

# Read from environment — set in docker-compose
EXERCISES_DIR = os.environ.get("EXERCISES_DIR", "./data/exercises")


# =============================================================================
# Path helpers — single source of truth for all paths
# =============================================================================

def exercise_dir(exercise_id: str) -> str:
    return os.path.join(EXERCISES_DIR, exercise_id)

def frames_dir(exercise_id: str) -> str:
    return os.path.join(exercise_dir(exercise_id), "frames")

def media_dir(exercise_id: str) -> str:
    return os.path.join(exercise_dir(exercise_id), "media")

def config_path(exercise_id: str) -> str:
    return os.path.join(exercise_dir(exercise_id), "config.json")

def frame_path(exercise_id: str, frame_index: int) -> str:
    return os.path.join(frames_dir(exercise_id), f"frame_{frame_index:03d}.json")

def frame_image_path(exercise_id: str, frame_index: int) -> str:
    return os.path.join(frames_dir(exercise_id), f"frame_{frame_index:03d}.png")


# =============================================================================
# JSON helpers
# =============================================================================

def save_frame_image(exercise_id: str, frame_index: int, image_bytes: bytes) -> str:
    """Save a PNG image for a frame. Returns the path written."""
    path = frame_image_path(exercise_id, frame_index)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


def get_frame_image(exercise_id: str, frame_index: int) -> bytes:
    """Return raw image bytes for a frame. Raises FileNotFoundError if missing."""
    path = frame_image_path(exercise_id, frame_index)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No image for frame {frame_index} in exercise '{exercise_id}'")
    with open(path, "rb") as f:
        return f.read()


def _read_json(path: str):
    with open(path, "r") as f:
        return json.load(f)

def _write_json(path: str, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# =============================================================================
# Exercise operations
# =============================================================================

def exercise_exists(exercise_id: str) -> bool:
    return os.path.isfile(config_path(exercise_id))


def create_exercise(name: str, frames: list, pose_engine: str = "mediapipe",
                    media_bytes: bytes = None, media_ext: str = ".mp4") -> dict:
    """
    Create a new exercise on disk.

    Args:
        name:        Human-readable exercise name.
        frames:      List of frame dicts, each with "keypoints" and "nao_angles".
                     Order in the list becomes frame_000, frame_001, …
        pose_engine: "mediapipe" or "yolo".
        media_bytes: Raw bytes of the original uploaded file, or None.
        media_ext:   File extension for the media file, e.g. ".mp4" or ".jpg".

    Returns:
        The config dict of the newly created exercise.
    """
    exercise_id = uuid.uuid4().hex[:8]

    os.makedirs(frames_dir(exercise_id), exist_ok=True)
    os.makedirs(media_dir(exercise_id), exist_ok=True)

    # Write frames
    for idx, frame_data in enumerate(frames):
        frame = {
            "frame_index": idx,
            "keypoints": frame_data.get("keypoints", {}),
            "nao_angles": frame_data.get("nao_angles", []),
        }
        _write_json(frame_path(exercise_id, idx), frame)

    # Save media file if provided
    if media_bytes is not None:
        ext = media_ext if media_ext.startswith(".") else f".{media_ext}"
        media_file = os.path.join(media_dir(exercise_id), f"original{ext}")
        with open(media_file, "wb") as f:
            f.write(media_bytes)

    # Build and save config
    config = {
        "id": exercise_id,
        "name": name,
        "created_at": datetime.utcnow().isoformat(),
        "pose_engine": pose_engine,
        "repetitions": 1,
        "frame_sequence": list(range(len(frames))),
    }
    _write_json(config_path(exercise_id), config)

    return config


def get_exercise(exercise_id: str) -> dict:
    """Return the config dict for an exercise. Raises FileNotFoundError if missing."""
    return _read_json(config_path(exercise_id))


def list_exercises() -> list:
    """
    Return a summary list of all exercises.
    Each entry: {id, name, frame_count, created_at, pose_engine, repetitions}
    """
    if not os.path.isdir(EXERCISES_DIR):
        return []

    result = []
    for entry in os.scandir(EXERCISES_DIR):
        if not entry.is_dir():
            continue
        cfg_path = os.path.join(entry.path, "config.json")
        if not os.path.isfile(cfg_path):
            continue
        try:
            cfg = _read_json(cfg_path)
            result.append({
                "id": cfg["id"],
                "name": cfg.get("name", ""),
                "frame_count": len(cfg.get("frame_sequence", [])),
                "created_at": cfg.get("created_at", ""),
                "pose_engine": cfg.get("pose_engine", ""),
                "repetitions": cfg.get("repetitions", 1),
                "calories": cfg.get("calories"),
                "description": cfg.get("description"),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    result.sort(key=lambda x: x["created_at"], reverse=True)
    return result


def delete_exercise(exercise_id: str) -> None:
    """Delete an entire exercise directory. Raises FileNotFoundError if missing."""
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")
    shutil.rmtree(exercise_dir(exercise_id))


def update_config(exercise_id: str, name: str = None, repetitions: int = None,
                  calories: float = None, description: str = None) -> dict:
    """
    Update name, repetitions, calorie estimate, and/or description in config.json.
    Returns the updated config dict.
    """
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    cfg = _read_json(config_path(exercise_id))
    if name is not None:
        cfg["name"] = name
    if repetitions is not None:
        cfg["repetitions"] = repetitions
    if calories is not None:
        cfg["calories"] = calories
    if description is not None:
        cfg["description"] = description
    _write_json(config_path(exercise_id), cfg)
    return cfg


# =============================================================================
# Frame sequence operations
# =============================================================================

def update_sequence(exercise_id: str, frame_sequence: list) -> dict:
    """
    Replace the frame_sequence in config.json.
    Validates that all referenced indices exist on disk.
    Returns the updated config dict.
    """
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    # Validate all indices exist
    for idx in frame_sequence:
        if not os.path.isfile(frame_path(exercise_id, idx)):
            raise ValueError(f"Frame index {idx} does not exist for exercise '{exercise_id}'")

    cfg = _read_json(config_path(exercise_id))
    cfg["frame_sequence"] = frame_sequence
    _write_json(config_path(exercise_id), cfg)
    return cfg


def get_frames(exercise_id: str) -> list:
    """
    Return all frames in frame_sequence order.
    Each item is the parsed frame_NNN.json dict.
    """
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    cfg = _read_json(config_path(exercise_id))
    sequence = cfg.get("frame_sequence", [])

    frames = []
    for idx in sequence:
        path = frame_path(exercise_id, idx)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Frame file missing for index {idx} in exercise '{exercise_id}'")
        frames.append(_read_json(path))
    return frames


# =============================================================================
# Single frame operations
# =============================================================================

def get_frame(exercise_id: str, frame_index: int) -> dict:
    """Return one frame by its on-disk index. Raises FileNotFoundError if missing."""
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    path = frame_path(exercise_id, frame_index)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Frame {frame_index} not found in exercise '{exercise_id}'")
    return _read_json(path)


def update_frame(exercise_id: str, frame_index: int,
                 nao_angles: list = None, keypoints: dict = None) -> dict:
    """
    Edit nao_angles and/or keypoints of an existing frame.
    Returns the updated frame dict.
    """
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    path = frame_path(exercise_id, frame_index)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Frame {frame_index} not found in exercise '{exercise_id}'")

    frame = _read_json(path)
    if nao_angles is not None:
        frame["nao_angles"] = nao_angles
    if keypoints is not None:
        frame["keypoints"] = keypoints
    _write_json(path, frame)
    return frame


def insert_frame(exercise_id: str, position: int, keypoints: dict, nao_angles: list) -> dict:
    """
    Insert a new frame at a specific position in frame_sequence.
    The frame file gets the next available index on disk; position controls
    where it appears in playback order.
    Returns the new frame dict.
    """
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    existing = [
        int(fname[6:9])
        for fname in os.listdir(frames_dir(exercise_id))
        if fname.startswith("frame_") and fname.endswith(".json")
    ]
    new_index = max(existing) + 1 if existing else 0

    frame = {
        "frame_index": new_index,
        "keypoints": keypoints,
        "nao_angles": nao_angles,
    }
    _write_json(frame_path(exercise_id, new_index), frame)

    cfg = _read_json(config_path(exercise_id))
    seq = cfg.get("frame_sequence", [])
    position = max(0, min(position, len(seq)))
    seq.insert(position, new_index)
    cfg["frame_sequence"] = seq
    _write_json(config_path(exercise_id), cfg)

    return frame


def add_frame(exercise_id: str, keypoints: dict, nao_angles: list) -> dict:
    """
    Append a new frame to an exercise.
    The new frame gets the next available index (max existing + 1).
    It is also appended to frame_sequence in config.json.
    Returns the new frame dict.
    """
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    # Find next index
    existing = [
        int(fname[6:9])
        for fname in os.listdir(frames_dir(exercise_id))
        if fname.startswith("frame_") and fname.endswith(".json")
    ]
    new_index = max(existing) + 1 if existing else 0

    frame = {
        "frame_index": new_index,
        "keypoints": keypoints,
        "nao_angles": nao_angles,
    }
    _write_json(frame_path(exercise_id, new_index), frame)

    # Append to sequence
    cfg = _read_json(config_path(exercise_id))
    cfg["frame_sequence"].append(new_index)
    _write_json(config_path(exercise_id), cfg)

    return frame


def delete_frame(exercise_id: str, frame_index: int) -> dict:
    """
    Remove a frame file and all its occurrences from frame_sequence.
    Returns the updated config dict.
    """
    if not exercise_exists(exercise_id):
        raise FileNotFoundError(f"Exercise '{exercise_id}' not found")

    path = frame_path(exercise_id, frame_index)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Frame {frame_index} not found in exercise '{exercise_id}'")

    os.remove(path)

    img_path = frame_image_path(exercise_id, frame_index)
    if os.path.isfile(img_path):
        os.remove(img_path)

    cfg = _read_json(config_path(exercise_id))
    cfg["frame_sequence"] = [i for i in cfg["frame_sequence"] if i != frame_index]
    _write_json(config_path(exercise_id), cfg)
    return cfg
