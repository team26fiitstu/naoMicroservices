#!/usr/bin/env python3
"""
video_pose_processor.py

Helper for:
  - Sending a video to MediaPipe pose_from_video
  - Decoding per-frame visualizations to PNGs
  - Filtering out frames with incomplete landmarks (missing x/y/z)
  - Returning only valid frames' landmarks for further processing
"""

import base64
import json
import os
from typing import Dict, Any, List

import requests
NO_NAMING = os.environ.get('NO_NAMING', True)
print(NO_NAMING)
print("NOOOO NAMING")
if NO_NAMING:
    POSE_FROM_VIDEO_URL = "http://localhost:6001/media_pipe_pose/pose_from_video"
else:
    POSE_FROM_VIDEO_URL = "http://skeletonFinderAPI:6001/media_pipe_pose/pose_from_video"
#POSE_FROM_VIDEO_URL = "http://localhost:6001/media_pipe_pose/pose_from_video"

REQUIRED_JOINTS = [
    "Left shoulder",
    "Right shoulder",
    "Left elbow",
    "Right elbow",
    "Left wrist",
    "Right wrist",
]
REQUIRED_COORDS = ["x", "y", "z"]


def _frame_has_complete_landmarks(frame_dict: Dict[str, Any]) -> bool:
    """
    Check if a single frame dict has all required joints and x/y/z coords.
    Assumes frame_dict is already stripped of 'visualization_base64'.
    """
    for joint in REQUIRED_JOINTS:
        joint_data = frame_dict.get(joint)
        if not isinstance(joint_data, dict):
            return False
        for c in REQUIRED_COORDS:
            if c not in joint_data:
                return False
    return True


def process_video_bytes(
    video_bytes: bytes,
    output_dir: str,
    number_frames_per_sec: int = 1,
    number_seconds_to_process: int = -1,
    attach_visualization: bool = True,
) -> Dict[str, Any]:
    """
    Send a video to pose_from_video, write debug images and JSON landmarks,
    and return only frames with complete landmarks.

    Args:
        video_bytes: raw bytes of the uploaded video
        output_dir: directory where frames & JSON files will be written
        number_frames_per_sec: sampling rate for pose_from_video
        number_seconds_to_process: -1 = full video
        attach_visualization: ask pose service to add visualization_base64

    Returns:
        dict with:
          - total_frames: int
          - valid_frames: int
          - invalid_frames: int
          - valid_landmarks: list[dict] (only joints/coords)
          - valid_image_paths: list[str]
          - invalid_image_paths: list[str]
          - landmarks_valid_json: str (path)
          - landmarks_all_json: str (path)
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1) Call pose_from_video
    encoded_video = base64.b64encode(video_bytes).decode("utf-8")

    resp = requests.post(
        POSE_FROM_VIDEO_URL,
        params={
            "number_frames_per_sec": number_frames_per_sec,
            "number_seconds_to_process": number_seconds_to_process,
            "attach_visualization": "true" if attach_visualization else "false",
        },
        data=encoded_video,
        timeout=60,
    )
    resp.raise_for_status()
    frames = resp.json()

    if not isinstance(frames, list):
        raise ValueError("pose_from_video response is not a list of frames")

    total_frames = len(frames)
    valid_landmarks: List[Dict[str, Any]] = []
    all_landmarks: List[Dict[str, Any]] = []

    valid_image_paths: List[str] = []
    invalid_image_paths: List[str] = []

    # 2) Per-frame processing
    for i, frame in enumerate(frames):
        # Save visualization image if present
        vis_b64 = frame.get("visualization_base64")
        img_path = None

        # Extract only landmarks (remove visualization_base64)
        landmarks_dict = {
            name: value
            for name, value in frame.items()
            if name != "visualization_base64"
        }

        is_complete = _frame_has_complete_landmarks(landmarks_dict)

        # Decide filename based on completeness
        if vis_b64 is not None:
            if is_complete:
                img_filename = f"frame_{i:04d}.png"
            else:
                img_filename = f"frame_{i:04d}_bad.png"

            img_path = os.path.join(output_dir, img_filename)
            try:
                img_bytes = base64.b64decode(vis_b64)
                with open(img_path, "wb") as f_img:
                    f_img.write(img_bytes)
            except Exception:
                # Don't crash the whole pipeline if saving fails
                img_path = None

        all_landmarks.append(landmarks_dict)

        if is_complete:
            valid_landmarks.append(landmarks_dict)
            if img_path:
                valid_image_paths.append(img_path)
        else:
            if img_path:
                invalid_image_paths.append(img_path)

    # 3) Save JSON summaries
    landmarks_valid_json = os.path.join(output_dir, "landmarks_valid.json")
    with open(landmarks_valid_json, "w") as f_json:
        json.dump(valid_landmarks, f_json, indent=2)

    landmarks_all_json = os.path.join(output_dir, "landmarks_all.json")
    with open(landmarks_all_json, "w") as f_json:
        json.dump(all_landmarks, f_json, indent=2)

    return {
        "total_frames": total_frames,
        "valid_frames": len(valid_landmarks),
        "invalid_frames": total_frames - len(valid_landmarks),
        "valid_landmarks": valid_landmarks,
        "valid_image_paths": valid_image_paths,
        "invalid_image_paths": invalid_image_paths,
        "landmarks_valid_json": landmarks_valid_json,
        "landmarks_all_json": landmarks_all_json,
    }
