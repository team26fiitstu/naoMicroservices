"""Hardware-free tests for the documented asynchronous run API."""
import sys
import threading
import time
from unittest.mock import patch

import requests

from tests._support import OfflineCase, ROOT, load_module, response

TRANSLATOR_DIR = ROOT / "services/translator"
sys.path.insert(0, str(TRANSLATOR_DIR))
with patch("os.makedirs"):
    translator = load_module("offline_choreography_translator", TRANSLATOR_DIR / "nao_pose_service.py")
translator.app.config.update(TESTING=True)

CHOREO = "aaaaaaaa"
OTHER = "bbbbbbbb"
FIRST = "11111111"
SECOND = "22222222"


def graph(choreography_id=CHOREO):
    return {"schema_version": 1, "id": choreography_id, "initial_state": FIRST,
            "states": [{"state_id": FIRST}, {"state_id": SECOND}],
            "transitions": [{"id": "go", "from": FIRST, "to": SECOND, "label": "go"},
                            {"id": "back", "from": SECOND, "to": FIRST, "label": "back"}]}


class ChoreographyRun(OfflineCase):
    def setUp(self):
        super().setUp()
        with translator._run_registry_lock:
            translator._runs.clear()
            translator._current_run_id = None
            translator._starting = False
        self.client = translator.app.test_client()
        self.calls = []

        def upstream(method, url, **kwargs):
            if "/choreography/" in url:
                return response(graph(OTHER if url.endswith(OTHER) else CHOREO))
            if url.endswith("/frames"):
                exercise_id = url.split("/")[-2]
                return response([{"frame_index": 1, "voice_lines": {"text": exercise_id}, "nao_angles": [1]},
                                 {"frame_index": 0, "nao_angles": [0]}])
            return response({"repetitions": 2})

        self.upstream = patch.object(translator, "request_with_retries", side_effect=upstream)
        self.upstream.start()
        self.addCleanup(self.upstream.stop)
        self.move = patch.object(translator, "call_nao_set_pose", side_effect=lambda angles: self.calls.append(("pose", angles)) or {"success": True})
        self.speak = patch.object(translator, "call_nao_voice_lines", side_effect=lambda lines: self.calls.append(("voice", lines)) or {"success": True})
        self.move.start()
        self.speak.start()
        self.addCleanup(self.move.stop)
        self.addCleanup(self.speak.stop)

    def wait_status(self, run_id, status):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            current = self.client.get(f"/run/{run_id}").json
            if current["status"] == status:
                return current
            time.sleep(0.005)
        self.fail(f"run did not reach {status}: {current}")

    def start(self, choreography_id=CHOREO):
        result = self.client.post(f"/choreography/{choreography_id}/run")
        if result.status_code == 202:
            self.run_id = result.json["run_id"]
        return result

    def test_start_async_order_state_and_outgoing_transitions(self):
        result = self.start()
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.json["status"], "performing")
        run = self.wait_status(self.run_id, "waiting")
        self.assertEqual(run["state_id"], FIRST)
        self.assertEqual([t["id"] for t in run["outgoing_transitions"]], ["go"])
        self.assertEqual(run["playback"]["repetitions"], 2)
        self.assertEqual(self.calls, [("voice", {"text": FIRST}), ("pose", [1]), ("pose", [0])] * 2)
        self.assertEqual(self.client.get("/run/current").json["run_id"], self.run_id)

    def test_wrong_signal_and_goto_send_no_robot_commands(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        self.calls.clear()
        wrong = self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "back"})
        self.assertEqual(wrong.status_code, 409)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.get(f"/run/{self.run_id}").json["state_id"], FIRST)
        direct = self.client.post(f"/run/{self.run_id}/goto", json={"state_id": SECOND})
        self.assertEqual((direct.status_code, direct.json["state_id"]), (200, SECOND))
        self.assertEqual(direct.json["status"], "waiting")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"}).status_code, 409)
        accepted = self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "back"})
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(self.wait_status(self.run_id, "waiting")["state_id"], FIRST)
        self.assertEqual(len(self.calls), 6)

    def test_only_one_active_run_and_stop(self):
        self.assertEqual(self.client.get("/run/current").status_code, 404)
        self.start()
        self.wait_status(self.run_id, "waiting")
        self.assertEqual(self.start(OTHER).status_code, 409)
        self.assertEqual(self.start().status_code, 409)
        stopped = self.client.post(f"/run/{self.run_id}/stop")
        self.assertEqual((stopped.status_code, stopped.json["status"]), (200, "stopped"))
        self.assertEqual(self.client.get("/run/current").status_code, 404)
        self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 409)
        self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"}).status_code, 409)
        self.assertEqual(self.start(OTHER).status_code, 202)
        self.wait_status(self.run_id, "waiting")

    def test_invalid_unknown_empty_and_unavailable(self):
        self.assertEqual(self.start("bad").status_code, 400)
        with patch.object(translator, "request_with_retries", return_value=response({}, 404)):
            self.assertEqual(self.start().status_code, 404)
        with patch.object(translator, "request_with_retries", side_effect=requests.ConnectionError("down")):
            self.assertEqual(self.start().status_code, 502)
        with patch.object(translator, "request_with_retries", return_value=response(dict(graph(), states=[]))):
            self.assertEqual(self.start().status_code, 502)
        with patch.object(translator, "request_with_retries", side_effect=lambda method, url, **kw: response(graph()) if "/choreography/" in url else response([])):
            self.assertEqual(self.start().status_code, 202)
            self.assertIn("no frames", self.wait_status(self.run_id, "stopped")["error"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.get("/run/current").status_code, 404)
        self.assertEqual(self.client.get("/run/no-such-id").status_code, 404)

    def test_signal_failure_keeps_source_and_reports_error(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        self.calls.clear()
        with patch.object(translator, "call_nao_set_pose", side_effect=requests.Timeout("robot")):
            accepted = self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"})
            self.assertEqual(accepted.status_code, 202)
            run = self.wait_status(self.run_id, "waiting")
        self.assertEqual(run["state_id"], FIRST)
        self.assertIn("robot playback failed", run["error"])
        self.assertEqual(self.calls, [("voice", {"text": SECOND})])

    def test_unavailable_target_keeps_source_without_robot_calls(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        self.calls.clear()

        def unavailable(method, url, **kwargs):
            if url.endswith(f"/exercise/{SECOND}/frames"):
                raise requests.ConnectionError("exercise service down")
            return response({"repetitions": 1})

        with patch.object(translator, "request_with_retries", side_effect=unavailable):
            self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"}).status_code, 202)
            run = self.wait_status(self.run_id, "waiting")
        self.assertEqual(run["state_id"], FIRST)
        self.assertIn("failed to fetch frames", run["error"])
        self.assertEqual(self.calls, [])

    def test_stop_between_frames(self):
        entered = threading.Event()
        release = threading.Event()
        commands = []

        def slow_pose(angles):
            commands.append(angles)
            entered.set()
            release.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_set_pose", side_effect=slow_pose):
            result = self.start()
            self.assertEqual(result.status_code, 202)
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"}).status_code, 409)
            self.assertEqual(self.client.post(f"/run/{self.run_id}/goto", json={"state_id": SECOND}).status_code, 409)
            self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 200)
            self.assertEqual(self.start(OTHER).status_code, 409)
            release.set()
            self.wait_status(self.run_id, "stopped")
        self.assertEqual(commands, [[1]])
        self.assertEqual(self.client.get("/run/current").status_code, 404)

    def test_stop_during_second_performance_keeps_robot_reserved(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        entered = threading.Event()
        release = threading.Event()

        def slow_pose(angles):
            entered.set()
            release.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_set_pose", side_effect=slow_pose):
            self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"}).status_code, 202)
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 200)
            self.assertEqual(self.start(OTHER).status_code, 409)
            release.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and translator._current_run_id is not None:
            time.sleep(0.005)
        self.assertIsNone(translator._current_run_id)

    def test_legacy_exercise_contract(self):
        result = self.client.post(f"/exercise/{FIRST}/run", json={"repetitions": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["total_poses_sent"], 3)
