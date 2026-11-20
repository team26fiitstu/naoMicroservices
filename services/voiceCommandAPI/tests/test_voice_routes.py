"""Offline HTTP contract tests for voice commands."""
import os
import sys
from http.client import RemoteDisconnected
from unittest.mock import patch

import requests
from urllib3 import exceptions as urllib3_exceptions

from tests._support import OfflineCase, ROOT, load_module, response

VOICE_DIR = ROOT / "services/voiceCommandAPI"
sys.path.insert(0, str(VOICE_DIR))
voice = load_module("offline_voice_server", VOICE_DIR / "server.py")
voice.app.config.update(TESTING=True)


class VoiceRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        self.client = voice.app.test_client()

    def test_commands_and_pose_lookup_do_not_call_robot(self):
        listed = self.client.get("/commands")
        self.assertEqual(listed.status_code, 200)
        self.assertIn("wave", listed.json["commands"])
        self.assertIn("hello", listed.json["aliases"])
        self.assertEqual(listed.json["descriptions"]["wave"], "Wave with the right arm")

        pose = self.client.get("/pose/hello")
        self.assertEqual(pose.status_code, 200)
        self.assertEqual(pose.json["name"], "wave")
        self.assertEqual(pose.json["description"], listed.json["descriptions"]["wave"])
        self.assertEqual(len(pose.json["angles"]), 22)
        unknown = self.client.get("/pose/not_a_pose")
        self.assertEqual(unknown.status_code, 404)
        self.assertIn("wave", unknown.json["available_commands"])

    def test_command_sends_resolved_angles_to_nao(self):
        expected_angles = self.client.get("/pose/wave").json["angles"]
        with patch.object(voice.requests, "post", return_value=response({"success": True})) as upstream:
            result = self.client.post("/command", json={"command": " hello "})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["command"], "wave")
        self.assertEqual(result.json["nao_response"], {"success": True})
        self.assertEqual(result.json["description"], "Wave with the right arm")
        upstream.assert_called_once_with(
            voice.NAO_SET_POSE_URL, json={"angles": expected_angles}, timeout=15,
        )

    def test_invalid_commands_do_not_contact_nao(self):
        with patch.object(voice.requests, "post") as upstream:
            for body in ({}, {"command": "   "}, {"command": "unknown"}):
                with self.subTest(body=body):
                    result = self.client.post("/command", json=body)
                    self.assertEqual(result.status_code, 400)
                    self.assertIn("error", result.json)
            malformed = self.client.post("/command", data="not json", content_type="application/json")
            self.assertEqual(malformed.status_code, 400)
            self.assertIn("error", malformed.json)
        upstream.assert_not_called()

    def test_nao_api_failure_returns_502(self):
        # setPose is not idempotent: a refused connection (request never sent)
        # is retried, but an HTTP 5xx / timeout / aborted connection must not
        # repeat the robot move.
        refused = requests.ConnectionError(urllib3_exceptions.MaxRetryError(
            None, "/setPose", urllib3_exceptions.NewConnectionError(None, "refused")))
        aborted = requests.ConnectionError(urllib3_exceptions.ProtocolError(
            "Connection aborted.", RemoteDisconnected("closed")))
        failures = (
            (refused, 3),
            (aborted, 1),
            (requests.ReadTimeout("NAO too slow"), 1),
            (response({"error": "down"}, 503), 1),
        )
        for failure, expected_calls in failures:
            with self.subTest(failure=failure):
                with patch.dict(os.environ, {"HTTP_RETRY_BACKOFF_SECONDS": "0"}), \
                        patch.object(voice.requests, "post", side_effect=failure if isinstance(failure, Exception) else None,
                                     return_value=None if isinstance(failure, Exception) else failure) as upstream:
                    result = self.client.post("/command", json={"command": "wave"})
                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.json["command"], "wave")
                self.assertIn("failed to reach NAO robot API", result.json["error"])
                self.assertEqual(upstream.call_count, expected_calls)
