"""Offline HTTP tests for translator routes."""
import io
import sys
from unittest.mock import patch

import requests
from werkzeug.datastructures import FileStorage

from _support import OfflineCase, ROOT, load_module, response

TRANSLATOR_DIR = ROOT / "services/translator"
sys.path.insert(0, str(TRANSLATOR_DIR))
with patch("os.makedirs"):
    translator = load_module("offline_translator_server", TRANSLATOR_DIR / "nao_pose_service.py")
translator.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

LANDMARKS = {
    name: {"x": x, "y": y, "z": -0.2}
    for name, x, y in (
        ("Left shoulder", .6, .4), ("Right shoulder", .4, .4),
        ("Left elbow", .7, .5), ("Right elbow", .3, .5),
        ("Left wrist", .8, .6), ("Right wrist", .2, .6),
    )
}
ANGLES = {"angles": [0.1] * 22}
ANGLES.update({key: 0.1 for key in (
    "LShoulderPitch", "LShoulderRoll", "LElbowRoll", "LElbowYaw",
    "RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RElbowYaw",
)})
SUMMARY = {
    "total_frames": 1, "valid_frames": 1, "invalid_frames": 0,
    "valid_landmarks": [LANDMARKS], "valid_image_paths": [],
    "invalid_image_paths": [], "landmarks_valid_json": "stub.json",
    "landmarks_all_json": "stub-all.json",
}


class TranslatorRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        self.client = translator.app.test_client()

    def upload(self, route, field, data=b"fake-media", **fields):
        fields[field] = (io.BytesIO(data), "sample." + ("jpg" if field == "image" else "mp4"))
        return self.client.post(route, data=fields)

    def test_health_and_landmarks(self):
        self.assertEqual(self.client.get("/test").status_code, 200)
        with patch.object(translator, "translate_arms", return_value=ANGLES) as convert:
            result = self.client.post("/arms/from_landmarks", json=LANDMARKS)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["nao_angles"], ANGLES["angles"])
        convert.assert_called_once_with(LANDMARKS)
        self.assertEqual(self.client.post("/arms/from_landmarks", data="bad").status_code, 400)
        self.assertEqual(self.client.post("/arms/from_landmarks", json={"Nose": {}}).status_code, 400)
        with patch.object(translator, "translate_arms", side_effect=ValueError("bad pose")):
            self.assertEqual(self.client.post("/arms/from_landmarks", json=LANDMARKS).status_code, 500)

    def test_image_exercise(self):
        with patch.object(translator.requests, "post", side_effect=[response(LANDMARKS), response({"id": "ex1"}, 201)]) as post, patch.object(translator, "translate_arms", return_value=ANGLES):
            result = self.upload("/exercise/from_image", "image", name="demo")
        self.assertEqual((result.status_code, result.json["id"]), (201, "ex1"))
        self.assertEqual(post.call_count, 2)
        self.assertEqual(self.client.post("/exercise/from_image").status_code, 400)
        with patch.object(translator.requests, "post", return_value=response({}, 200)):
            self.assertEqual(self.upload("/exercise/from_image", "image").status_code, 422)
        with patch.object(translator.requests, "post", side_effect=requests.Timeout("pose timeout")):
            self.assertEqual(self.upload("/exercise/from_image", "image").status_code, 502)

    def test_image_robot_route(self):
        with patch.object(translator, "call_pose_service", return_value=LANDMARKS), patch.object(translator, "translate_arms", return_value=ANGLES), patch.object(translator, "call_nao_set_pose", return_value={"success": True}) as nao, patch.object(FileStorage, "save"):
            result = self.upload("/arms/from_image", "image")
        self.assertEqual(result.status_code, 200)
        nao.assert_called_once_with(ANGLES["angles"])
        self.assertEqual(self.client.post("/arms/from_image").status_code, 400)
        with patch("werkzeug.datastructures.FileStorage.save"), patch.object(translator, "call_pose_service", side_effect=requests.Timeout("pose")):
            self.assertEqual(self.upload("/arms/from_image", "image").status_code, 502)

    def test_video_routes(self):
        for route, status in (("/exercise/from_video", 201), ("/arms/from_video", 200)):
            with self.subTest(route=route):
                with patch.object(translator, "process_video_bytes", return_value=dict(SUMMARY)), patch.object(translator, "translate_arms", return_value=ANGLES), patch.object(translator, "call_exercise_create", return_value={"id": "ex1"}), patch.object(translator, "call_nao_set_pose", return_value={"success": True}), patch.object(translator.os, "makedirs"):
                    result = self.upload(route, "video", fps="2")
                self.assertEqual(result.status_code, status)
                self.assertEqual(self.client.post(route).status_code, 400)
                self.assertEqual(self.upload(route, "video", fps="bad").status_code, 400)
                with patch.object(translator, "process_video_bytes", return_value=dict(SUMMARY, valid_frames=0)), patch.object(translator.os, "makedirs"):
                    self.assertEqual(self.upload(route, "video").status_code, 422)
                with patch.object(translator, "process_video_bytes", side_effect=requests.Timeout("pose")), patch.object(translator.os, "makedirs"):
                    self.assertEqual(self.upload(route, "video").status_code, 502)

    def test_video_max_frames_preserves_saved_payload(self):
        summary = dict(SUMMARY, valid_frames=2, valid_landmarks=[LANDMARKS, LANDMARKS], valid_image_paths=[])
        with patch.object(translator, "process_video_bytes", return_value=summary) as process, patch.object(translator, "translate_arms", return_value=ANGLES), patch.object(translator, "call_exercise_create", return_value={"id": "ex1"}) as create:
            result = self.upload("/exercise/from_video", "video", data=b"video-bytes", fps="2", seconds="5", max_frames="1", name="demo")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(len(create.call_args.kwargs["frames"]), 1)
        self.assertEqual(create.call_args.kwargs["frames"][0]["nao_angles"], ANGLES["angles"])
        self.assertEqual(create.call_args.kwargs["media_bytes"], b"video-bytes")
        self.assertEqual(create.call_args.kwargs["name"], "demo")
        self.assertEqual(process.call_args.kwargs["number_frames_per_sec"], 2)
        self.assertEqual(process.call_args.kwargs["number_seconds_to_process"], 5)

    def test_run_exercise(self):
        frames = [{"frame_index": 0, "nao_angles": [0.1] * 22}]
        with patch.object(translator.requests, "get", side_effect=[response(frames), response({"repetitions": 2})]), patch.object(translator, "call_nao_set_pose", return_value={"success": True}) as nao:
            result = self.client.post("/exercise/ex1/run", json={})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["total_poses_sent"], 2)
        self.assertEqual(nao.call_count, 2)
        with patch.object(translator.requests, "get", return_value=response([], 404)):
            self.assertEqual(self.client.post("/exercise/missing/run").status_code, 404)
        with patch.object(translator.requests, "get", return_value=response(frames)):
            self.assertEqual(self.client.post("/exercise/ex1/run", json={"repetitions": 0}).status_code, 400)
        with patch.object(translator.requests, "get", side_effect=requests.Timeout("config")):
            self.assertEqual(self.client.post("/exercise/ex1/run").status_code, 502)
        with patch.object(translator.requests, "get", return_value=response(frames)), patch.object(translator, "call_nao_set_pose", side_effect=requests.Timeout("robot")):
            result = self.client.post("/exercise/ex1/run", json={"repetitions": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["results"][0]["status"], "error")

    def test_run_preserves_stored_sequence_with_repeated_frames(self):
        frames = [
            {"frame_index": 1, "nao_angles": [0.1] * 22, "voice_lines": {"lang": "English"}},
            {"frame_index": 0, "nao_angles": [0.2] * 22},
            {"frame_index": 1, "nao_angles": [0.1] * 22},
        ]
        with patch.object(translator.requests, "get", return_value=response(frames)), patch.object(translator, "call_nao_set_pose", return_value={"success": True}) as move, patch.object(translator, "call_nao_voice_lines", return_value={"success": True}) as speak:
            result = self.client.post("/exercise/ex1/run", json={"repetitions": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual([call.args[0] for call in move.call_args_list], [[0.1] * 22, [0.2] * 22, [0.1] * 22])
        speak.assert_called_once_with({"lang": "English"})

    def test_crud_proxies(self):
        cases = (
            ("get", "/exercise/list", "get", None),
            ("get", "/exercise/ex1", "get", None),
            ("get", "/exercise/ex1/frames", "get", None),
            ("delete", "/exercise/ex1", "delete", None),
            ("put", "/exercise/ex1/config", "put", {"name": "new"}),
            ("put", "/exercise/ex1/sequence", "put", {"frame_sequence": [0]}),
        )
        for method, path, upstream_method, body in cases:
            with self.subTest(path=path, method=method):
                with patch.object(translator.requests, upstream_method, return_value=response({"ok": True}, 202)) as upstream:
                    result = getattr(self.client, method)(path, json=body)
                self.assertEqual((result.status_code, result.json), (202, {"ok": True}))
                upstream.assert_called_once()
                with patch.object(translator.requests, upstream_method, return_value=response({"error": "missing"}, 404)):
                    missing = getattr(self.client, method)(path, json=body)
                self.assertEqual(missing.status_code, 404)
