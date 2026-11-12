"""Offline Flask route tests. This directory is the explicit safe discovery target."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import requests
from werkzeug.datastructures import FileStorage

ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    result.raise_for_status.side_effect = (
        requests.HTTPError("upstream failed") if status >= 400 else None
    )
    return result


# Model modules are replaced before the skeleton server imports its blueprints.
SKELETON_DIR = ROOT / "services/skeletonFinderAPI/server"
sys.path.insert(0, str(SKELETON_DIR))
MODEL_NAMES = {
    "third_party_pose_estimation.media_pipe_model.pose_estimation_mediapipe":
        ("evaluate_pose_mediapipe", "evaluate_pose_from_video_mediapipe"),
    "third_party_pose_estimation.yolo_model.pose_estimate":
        ("evaluate_yolo_pose_from_video",),
    "third_party_pose_estimation.yolo_model.yolo_image_only": ("process_image",),
}
for module_name, functions in MODEL_NAMES.items():
    fake = types.ModuleType(module_name)
    for function in functions:
        setattr(fake, function, Mock(side_effect=AssertionError("model called without a test stub")))
    sys.modules[module_name] = fake
skeleton = load_module("offline_skeleton_server", SKELETON_DIR / "server.py")
skeleton.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
mediapipe = sys.modules[
    "third_party_pose_estimation.media_pipe_model.media_pipe_pose_api"
]
yolo = sys.modules["third_party_pose_estimation.yolo_model.yolo_pose_api"]

# The NAOqi interface is installed before *any* robot module is imported.
class FakeProxy:
    fail_on_motion = False

    def __init__(self, service, ip, port):
        self.service = service
        self.calls = []
        fake_proxies.append(self)

    def stiffnessInterpolation(self, *args):
        self.calls.append(("stiffnessInterpolation", args))

    def angleInterpolation(self, *args):
        self.calls.append(("angleInterpolation", args))
        if self.fail_on_motion:
            raise RuntimeError("fake motion failure")

    def setParameter(self, *args):
        self.calls.append(("setParameter", args))

    def say(self, *args):
        self.calls.append(("say", args))


fake_proxies = []
naoqi_stub = types.ModuleType("naoqi")
naoqi_stub.ALProxy = FakeProxy
sys.modules["naoqi"] = naoqi_stub
qi_stub = types.ModuleType("qi")
qi_stub.Session = Mock(side_effect=AssertionError("NAOqi session must never connect"))
sys.modules["qi"] = qi_stub
ROBOT_DIR = ROOT / "services/naoRobotAPI"
sys.path.insert(0, str(ROBOT_DIR))
robot = load_module("offline_nao_server", ROBOT_DIR / "server.py")
robot.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

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


class OfflineCase(unittest.TestCase):
    def setUp(self):
        # Any unpatched requests call fails before a socket can be opened.
        self.network_guard = patch.object(
            requests.sessions.Session, "request",
            side_effect=AssertionError("external HTTP request attempted"),
        )
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)


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


class SkeletonRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        self.client = skeleton.app.test_client()

    def test_health(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_post_pose_routes(self):
        cases = (
            ("/media_pipe_pose/pose_from_image", mediapipe, "evaluate_pose_mediapipe", {"joint": 1}),
            ("/media_pipe_pose/pose_from_video", mediapipe, "evaluate_pose_from_video_mediapipe", [{"joint": 1}]),
            ("/yolo_pose/pose_from_image", yolo, "process_image", {"person": 1}),
            ("/yolo_pose/pose_from_video", yolo, "evaluate_yolo_pose_from_video", [{"person": 1}]),
        )
        for path, module, function, payload in cases:
            with self.subTest(path=path):
                with patch.object(module, function, return_value=payload) as model:
                    result = self.client.post(path, data=b"encoded")
                self.assertEqual((result.status_code, result.json), (200, payload))
                model.assert_called_once()
                with patch.object(module, function, side_effect=ValueError("bad media")):
                    self.assertEqual(self.client.post(path, data=b"bad").status_code, 500)

    def test_get_pose_routes_and_missing_path(self):
        cases = (
            ("/media_pipe_pose/pose_from_image", mediapipe, "evaluate_pose_mediapipe", {"joint": 1}),
            ("/media_pipe_pose/pose_from_video", mediapipe, "evaluate_pose_from_video_mediapipe", [{"joint": 1}]),
            ("/yolo_pose/pose_from_image", yolo, "process_image", {"person": 1}),
            ("/yolo_pose/pose_from_video", yolo, "evaluate_yolo_pose_from_video", [{"person": 1}]),
        )
        for path, module, function, payload in cases:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 500)
                file_stub = patch.object(mediapipe.Image, "open") if module is mediapipe and "image" in path else patch("builtins.open")
                with file_stub, patch.object(module, function, return_value=payload) as model:
                    result = self.client.get(path, query_string={"file_location": "fake-media"})
                self.assertEqual((result.status_code, result.json), (200, payload))
                model.assert_called_once()
                if "video" in path:
                    self.assertEqual(self.client.get(path, query_string={"file_location": "fake", "number_frames_per_sec": "bad"}).status_code, 500)


class RobotRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        fake_proxies[:] = []
        FakeProxy.fail_on_motion = False
        self.client = robot.app.test_client()

    def test_health_and_pose(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        result = self.client.post("/setting_pose/setPose", json={"angles": [0.1] * 22})
        self.assertEqual((result.status_code, result.json), (200, {"success": True}))
        self.assertEqual(fake_proxies[0].service, "ALMotion")
        self.assertEqual([name for name, _ in fake_proxies[0].calls], ["stiffnessInterpolation", "angleInterpolation"])
        fake_proxies[:] = []
        for payload in ({}, {"angles": [1]}, {"angles": "bad"}):
            self.assertEqual(self.client.post("/setting_pose/setPose", json=payload).status_code, 400)
        self.assertEqual(self.client.post("/setting_pose/setPose", data="bad").status_code, 400)
        self.assertEqual(fake_proxies, [])
        FakeProxy.fail_on_motion = True
        self.assertEqual(self.client.post("/setting_pose/setPose", json={"angles": [0.1] * 22}).status_code, 500)
        self.assertEqual(fake_proxies[0].service, "ALMotion")

    def test_json_without_json_content_type(self):
        # Both routes accepted JSON regardless of Content-Type before input validation was added.
        from robot.voice_lines import voice_lines_api
        pose = self.client.post(
            "/setting_pose/setPose",
            data=json.dumps({"angles": [0.1] * 22}),
            content_type="text/plain",
        )
        self.assertEqual(pose.status_code, 200)
        self.assertEqual(fake_proxies[0].service, "ALMotion")
        with patch.object(voice_lines_api, "set_voice_lines") as speak:
            voice = self.client.post(
                "/voiceLines/applyVoiceLine",
                data=json.dumps({"voice_lines": {"lang": "English"}}),
                content_type="text/plain",
            )
        self.assertEqual(voice.status_code, 200)
        speak.assert_called_once_with({"lang": "English"})

    def test_voice_and_legacy_pose_routes(self):
        from robot.voice_lines import voice_lines_api
        from robot.setting_pose import setting_pose_api
        with patch.object(voice_lines_api, "set_voice_lines") as speak:
            result = self.client.post("/voiceLines/applyVoiceLine", json={"voice_lines": {"lang": "English"}})
        self.assertEqual((result.status_code, result.json), (200, {"success": True}))
        speak.assert_called_once_with({"lang": "English"})
        self.assertEqual(self.client.post("/voiceLines/applyVoiceLine", json={}).status_code, 400)
        with patch.object(voice_lines_api, "set_voice_lines", side_effect=RuntimeError("fake speech failure")):
            self.assertEqual(self.client.post("/voiceLines/applyVoiceLine", json={"voice_lines": {}}).status_code, 500)
        with patch.object(setting_pose_api, "set_nao_pose_mediapipe") as pose:
            result = self.client.post("/setting_pose/setPoseMediapipe", data="{}")
        self.assertEqual(result.status_code, 200)
        pose.assert_called_once_with("{}")
        self.assertEqual(fake_proxies, [])

    def test_movement_demo_uses_only_fake_interface(self):
        result = self.client.get("/tests/test")
        self.assertEqual((result.status_code, result.json), (200, {"success": True}))
        self.assertEqual(fake_proxies[0].service, "ALMotion")
        self.assertEqual(fake_proxies[0].calls[0][0], "stiffnessInterpolation")
        self.assertEqual(fake_proxies[0].calls[1][0], "angleInterpolation")


if __name__ == "__main__":
    unittest.main()
