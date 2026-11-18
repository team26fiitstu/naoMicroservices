"""Offline HTTP contract tests for voice commands."""
import sys
from unittest.mock import patch

import requests

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
        for failure in (requests.ConnectionError("NAO unavailable"), response({"error": "down"}, 503)):
            with self.subTest(failure=failure):
                with patch.object(voice.requests, "post", side_effect=failure if isinstance(failure, Exception) else None,
                                  return_value=None if isinstance(failure, Exception) else failure) as upstream:
                    result = self.client.post("/command", json={"command": "wave"})
                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.json["command"], "wave")
                self.assertIn("failed to reach NAO robot API", result.json["error"])
                upstream.assert_called_once()
