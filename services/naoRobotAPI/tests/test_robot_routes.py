"""Offline HTTP tests for naoRobotAPI routes."""
import json
import sys
import threading
import types
from unittest.mock import Mock, patch

from tests._support import OfflineCase, ROOT, load_module


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


class RobotRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        fake_proxies[:] = []
        FakeProxy.fail_on_motion = False
        robot._reservation.update(token=None, expires_at=0)
        self.client = robot.app.test_client()

    def test_health_and_pose(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        result = self.client.post("/setting_pose/setPose", json={"angles": [0.1] * 22})
        self.assertEqual((result.status_code, result.json), (200, {"success": True}))
        self.assertEqual(fake_proxies[0].service, "ALMotion")
        self.assertEqual([name for name, _ in fake_proxies[0].calls], ["stiffnessInterpolation", "angleInterpolation"])
        self.assertEqual(len(fake_proxies[0].calls[1][1][0]), 22)
        self.assertEqual(fake_proxies[0].calls[1][1][1], [0.1] * 22)
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

    def test_pose_and_voice_requests_share_robot_lock(self):
        from robot.setting_pose import setting_pose_api
        from robot.voice_lines import voice_lines_api

        pose_entered = threading.Event()
        release_pose = threading.Event()
        voice_entered = threading.Event()
        outcomes = []

        def slow_pose(angles):
            pose_entered.set()
            release_pose.wait(3)

        def speak(config):
            voice_entered.set()

        with patch.object(setting_pose_api, "set_nao_pose", side_effect=slow_pose), \
                patch.object(voice_lines_api, "set_voice_lines", side_effect=speak):
            pose_thread = threading.Thread(target=lambda: outcomes.append(
                robot.app.test_client().post("/setting_pose/setPose", json={"angles": [0.1] * 22}).status_code))
            voice_thread = threading.Thread(target=lambda: outcomes.append(
                robot.app.test_client().post("/voiceLines/applyVoiceLine", json={"voice_lines": {}}).status_code))
            pose_thread.start()
            try:
                self.assertTrue(pose_entered.wait(3))
                voice_thread.start()
                self.assertFalse(voice_entered.wait(0.1))
            finally:
                release_pose.set()
                pose_thread.join(3)
                if voice_thread.ident is not None:
                    voice_thread.join(3)

        self.assertEqual(outcomes, [200, 200])
        self.assertTrue(voice_entered.is_set())

    def test_choreography_reservation_blocks_other_robot_commands(self):
        from robot.voice_lines import voice_lines_api

        self.assertEqual(self.client.post("/control/reservation", json={"token": "run-a"}).status_code, 200)
        self.assertEqual(self.client.post("/control/reservation", json={"token": "run-b"}).status_code, 409)
        self.assertEqual(self.client.post("/setting_pose/setPose", json={"angles": [0.1] * 22}).status_code, 409)
        with patch.object(voice_lines_api, "set_voice_lines") as speak:
            self.assertEqual(self.client.post("/voiceLines/applyVoiceLine", json={"voice_lines": {}}).status_code, 409)
            speak.assert_not_called()
        result = self.client.post("/setting_pose/setPose", json={"angles": [0.1] * 22},
                                  headers={"X-Robot-Run-Token": "run-a"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.delete("/control/reservation", json={"token": "run-b"}).status_code, 409)
        self.assertEqual(self.client.delete("/control/reservation", json={"token": "run-a"}).status_code, 200)
        self.assertEqual(self.client.post("/setting_pose/setPose", json={"angles": [0.1] * 22}).status_code, 200)

    def test_reservation_can_renew_during_long_robot_call(self):
        from robot.setting_pose import setting_pose_api

        entered = threading.Event()
        release = threading.Event()

        def slow_pose(angles):
            entered.set()
            release.wait(3)

        self.assertEqual(self.client.post("/control/reservation", json={"token": "run-a"}).status_code, 200)
        with patch.object(setting_pose_api, "set_nao_pose", side_effect=slow_pose):
            worker = threading.Thread(target=lambda: robot.app.test_client().post(
                "/setting_pose/setPose", json={"angles": [0.1] * 22},
                headers={"X-Robot-Run-Token": "run-a"}))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.client.post("/control/reservation", json={"token": "run-a"}).status_code, 200)
            finally:
                release.set()
                worker.join(3)
        self.assertEqual(self.client.delete("/control/reservation", json={"token": "run-a"}).status_code, 200)

    def test_reservation_rejects_in_progress_direct_command(self):
        from robot.setting_pose import setting_pose_api

        entered = threading.Event()
        release = threading.Event()

        def slow_pose(angles):
            entered.set()
            release.wait(3)

        with patch.object(setting_pose_api, "set_nao_pose", side_effect=slow_pose):
            worker = threading.Thread(target=lambda: robot.app.test_client().post(
                "/setting_pose/setPose", json={"angles": [0.1] * 22}))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.client.post("/control/reservation", json={"token": "run-a"}).status_code, 409)
            finally:
                release.set()
                worker.join(3)
        self.assertIsNone(robot._reservation["token"])

    def test_reservation_expires_if_owner_disappears(self):
        self.assertEqual(self.client.post("/control/reservation", json={"token": "run-a"}).status_code, 200)
        after_expiry = robot._reservation["expires_at"] + 1
        with patch.object(robot.time, "time", return_value=after_expiry):
            result = self.client.post("/setting_pose/setPose", json={"angles": [0.1] * 22})
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(robot._reservation["token"])
