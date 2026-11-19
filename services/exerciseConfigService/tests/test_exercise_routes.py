"""Offline HTTP contract tests for exercise configuration."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import requests

from tests._support import OfflineCase, ROOT, response

SERVICE_DIR = ROOT / "services/exerciseConfigService"
sys.path.insert(0, str(SERVICE_DIR))
from app import create_app  # noqa: E402
from app import storage  # noqa: E402
from app.routes import exercise  # noqa: E402


class ExerciseRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"EXERCISES_DIR": temporary.name})
        environment.start()
        self.addCleanup(environment.stop)
        storage_dir = patch.object(storage, "EXERCISES_DIR", temporary.name)
        storage_dir.start()
        self.addCleanup(storage_dir.stop)
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def create_exercise(self):
        result = self.client.post("/exercise/create", json={
            "name": "Arm wave",
            "pose_engine": "mediapipe",
            "frames": [
                {"keypoints": {"arm": [1, 2]}, "nao_angles": [0.1, 0.2]},
                {"keypoints": {"arm": [3, 4]}, "nao_angles": [0.3, 0.4]},
            ],
        })
        self.assertEqual(result.status_code, 201)
        return result.json

    def test_create_get_list_update_and_delete(self):
        self.assertEqual(self.client.get("/exercise/list").json, [])
        created = self.create_exercise()
        exercise_id = created["id"]
        directory = self.root / exercise_id
        self.assertEqual(created["name"], "Arm wave")
        self.assertEqual(created["pose_engine"], "mediapipe")
        self.assertEqual(created["frame_sequence"], [0, 1])
        self.assertTrue((directory / "config.json").is_file())
        self.assertTrue((directory / "frames/frame_000.json").is_file())

        fetched = self.client.get(f"/exercise/{exercise_id}")
        self.assertEqual((fetched.status_code, fetched.json), (200, created))
        listed = self.client.get("/exercise/list")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json), 1)
        self.assertEqual(listed.json[0]["id"], exercise_id)
        self.assertEqual(listed.json[0]["frame_count"], 2)

        updated = self.client.put(f"/exercise/{exercise_id}/config", json={
            "name": "New name", "repetitions": 3, "calories": 12.5,
            "description": "Raise both arms",
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["name"], "New name")
        self.assertEqual(updated.json["repetitions"], 3)
        self.assertEqual(updated.json["calories"], 12.5)
        self.assertEqual(updated.json["description"], "Raise both arms")
        self.assertEqual(self.client.get(f"/exercise/{exercise_id}").json, updated.json)

        deleted = self.client.delete(f"/exercise/{exercise_id}")
        self.assertEqual((deleted.status_code, deleted.json), (200, {"deleted": exercise_id}))
        self.assertFalse(directory.exists())
        self.assertEqual(self.client.get("/exercise/list").json, [])
        self.assertEqual(self.client.get(f"/exercise/{exercise_id}").status_code, 404)

    def test_frames_and_sequence_persist_in_playback_order(self):
        exercise_id = self.create_exercise()["id"]
        base = f"/exercise/{exercise_id}"
        first = self.client.get(f"{base}/frame/0")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["keypoints"], {"arm": [1, 2]})

        changed = self.client.put(f"{base}/frame/0", json={"nao_angles": [0.9]})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json["nao_angles"], [0.9])
        self.assertEqual(self.client.get(f"{base}/frame/0").json["nao_angles"], [0.9])

        added = self.client.post(f"{base}/frame", json={
            "keypoints": {"arm": [5, 6]}, "nao_angles": [0.5],
        })
        self.assertEqual(added.status_code, 201)
        self.assertEqual(added.json["frame_index"], 2)
        self.assertEqual(self.client.get(base).json["frame_sequence"], [0, 1, 2])

        sequence = self.client.put(f"{base}/sequence", json={"frame_sequence": [2, 0, 2]})
        self.assertEqual(sequence.status_code, 200)
        self.assertEqual(sequence.json["frame_sequence"], [2, 0, 2])
        frames = self.client.get(f"{base}/frames")
        self.assertEqual(frames.status_code, 200)
        self.assertEqual([frame["frame_index"] for frame in frames.json], [2, 0, 2])
        self.assertEqual(frames.json[1]["nao_angles"], [0.9])

        removed = self.client.delete(f"{base}/frame/2")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json["frame_sequence"], [0])
        self.assertFalse((self.root / exercise_id / "frames/frame_002.json").exists())
        self.assertEqual(self.client.get(f"{base}/frame/2").status_code, 404)
        self.assertEqual([frame["frame_index"] for frame in self.client.get(f"{base}/frames").json], [0])

    def test_validation_does_not_change_stored_data(self):
        self.assertEqual(self.client.post("/exercise/create", json={"name": "Empty", "frames": []}).status_code, 400)
        self.assertEqual(self.client.get("/exercise/list").json, [])
        exercise_id = self.create_exercise()["id"]
        base = f"/exercise/{exercise_id}"
        original = self.client.get(base).json
        for body in ({"repetitions": 0}, {"calories": "invalid"}):
            with self.subTest(body=body):
                result = self.client.put(f"{base}/config", json=body)
                self.assertEqual(result.status_code, 400)
                self.assertIn("error", result.json)
        for body in ({}, {"frame_sequence": [0, 99]}):
            with self.subTest(body=body):
                result = self.client.put(f"{base}/sequence", json=body)
                self.assertEqual(result.status_code, 400)
                self.assertIn("error", result.json)
        self.assertEqual(self.client.post(f"{base}/frame", json={"keypoints": {}}).status_code, 400)
        self.assertEqual(self.client.put(f"{base}/frame/0", json={}).status_code, 400)
        self.assertEqual(self.client.get(base).json, original)
        self.assertEqual(self.client.get(f"{base}/frame/99").status_code, 404)

    def test_insert_pose_uses_stubbed_voice_service(self):
        exercise_id = self.create_exercise()["id"]
        base = f"/exercise/{exercise_id}"
        pose = {"name": "wave", "description": "Wave", "angles": [0.7, 0.8]}
        with patch.object(exercise.requests, "get", return_value=response(pose)) as upstream:
            inserted = self.client.post(f"{base}/frame/from_pose", json={
                "pose_name": "wave", "position": 1,
            })
        self.assertEqual(inserted.status_code, 201)
        self.assertEqual(inserted.json["pose_name"], "wave")
        self.assertEqual(inserted.json["inserted_at_position"], 1)
        self.assertEqual(inserted.json["frame"]["nao_angles"], pose["angles"])
        upstream.assert_called_once_with(f"{exercise.VOICE_COMMAND_API_URL}/pose/wave", timeout=10)
        self.assertEqual(self.client.get(base).json["frame_sequence"], [0, 2, 1])
        self.assertEqual(self.client.get(f"{base}/frames").json[1]["keypoints"], {"pose_name": "wave"})

        with patch.object(exercise.requests, "get", return_value=response({"error": "unknown pose"}, 404)):
            unknown = self.client.post(f"{base}/frame/from_pose", json={"pose_name": "bad", "position": 1})
        self.assertEqual(unknown.status_code, 400)
        with patch.object(exercise.requests, "get", side_effect=requests.Timeout("voice timeout")):
            unavailable = self.client.post(f"{base}/frame/from_pose", json={"pose_name": "wave", "position": 1})
        self.assertEqual(unavailable.status_code, 502)
        self.assertEqual(self.client.get(base).json["frame_sequence"], [0, 2, 1])
