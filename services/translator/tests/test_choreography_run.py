"""Hardware-free tests of choreography playback and run coordination."""
import sys
import threading
from unittest.mock import patch

import requests

from tests._support import OfflineCase, ROOT, load_module, response

TRANSLATOR_DIR = ROOT / "services/translator"
sys.path.insert(0, str(TRANSLATOR_DIR))
with patch("os.makedirs"):
    translator = load_module("offline_choreography_translator", TRANSLATOR_DIR / "nao_pose_service.py")
translator.app.config.update(TESTING=True)

CHOREO = "aaaaaaaa"
FIRST = "11111111"
SECOND = "22222222"
OTHER = "bbbbbbbb"


def graph(choreography_id=CHOREO):
    return {"schema_version": 1, "id": choreography_id, "initial_state": FIRST,
            "states": [{"state_id": FIRST}, {"state_id": SECOND}],
            "transitions": [{"id": "go", "from": FIRST, "to": SECOND, "label": "go"},
                            {"id": "back", "from": SECOND, "to": FIRST, "label": "back"}]}


class ChoreographyRun(OfflineCase):
    def setUp(self):
        super().setUp()
        translator._runs.clear()
        translator._run_locks.clear()
        self.client = translator.app.test_client()
        self.calls = []

        def upstream(method, url, **kwargs):
            if "/choreography/" in url:
                return response(graph(OTHER if url.endswith(OTHER) else CHOREO))
            if url.endswith("/frames"):
                exercise_id = url.split("/")[-2]
                return response([{"frame_index": 1, "voice_lines": {"text": exercise_id}, "nao_angles": [1]},
                                 {"frame_index": 0, "nao_angles": [0]},
                                 {"frame_index": 1, "nao_angles": [1]}])
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

    def start(self, choreography_id=CHOREO):
        return self.client.post(f"/choreography/{choreography_id}/run")

    def test_start_plays_initial_exercise_in_stored_order_and_repetitions(self):
        result = self.start()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["state"]["state_id"], FIRST)
        self.assertEqual(result.json["playback"]["repetitions"], 2)
        one_rep = [("voice", {"text": FIRST}), ("pose", [1]), ("pose", [0]), ("pose", [1])]
        self.assertEqual(self.calls, one_rep * 2)
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").json["state_id"], FIRST)

    def test_signal_and_direct_state_change(self):
        self.start()
        self.calls.clear()
        wrong = self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "back"})
        self.assertEqual(wrong.status_code, 409)
        self.assertIn("current state", wrong.json["error"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").json["state_id"], FIRST)

        direct = self.client.put(f"/choreography/{CHOREO}/run/state", json={"state_id": SECOND})
        self.assertEqual((direct.status_code, direct.json["state_id"]), (200, SECOND))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "go"}).status_code, 409)
        self.assertEqual(self.calls, [])
        moved = self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "back"})
        self.assertEqual((moved.status_code, moved.json["state"]["state_id"]), (200, FIRST))
        self.assertEqual(len(self.calls), 8)

    def test_stop_isolated_runs_and_repeated_operations(self):
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").status_code, 409)
        self.assertEqual(self.client.delete(f"/choreography/{CHOREO}/run").status_code, 409)
        self.start()
        self.assertEqual(self.start().status_code, 409)
        self.start(OTHER)
        self.assertEqual(self.client.delete(f"/choreography/{CHOREO}/run").json["active"], False)
        self.assertEqual(self.client.delete(f"/choreography/{CHOREO}/run").status_code, 409)
        self.calls.clear()
        self.assertEqual(self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "go"}).status_code, 409)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.get(f"/choreography/{OTHER}/run").json["state_id"], FIRST)

    def test_missing_invalid_empty_and_unavailable_upstream(self):
        self.assertEqual(self.start("bad").status_code, 400)
        self.assertEqual(self.client.post(f"/choreography/{CHOREO}/run/signal", json={}).status_code, 400)
        with patch.object(translator, "request_with_retries", return_value=response({}, 404)):
            self.assertEqual(self.start().status_code, 404)
        with patch.object(translator, "request_with_retries", side_effect=requests.ConnectionError("down")):
            self.assertEqual(self.start().status_code, 502)
        with patch.object(translator, "request_with_retries", return_value=response(dict(graph(), states=[{"state_id": []}]))):
            self.assertEqual(self.start().status_code, 502)
        with patch.object(translator, "request_with_retries", return_value=response(dict(graph(), initial_state=[]))):
            self.assertEqual(self.start().status_code, 502)
        with patch.object(translator, "request_with_retries", side_effect=lambda method, url, **kw: response(graph()) if "/choreography/" in url else response([])):
            self.assertEqual(self.start().status_code, 422)
        with patch.object(translator, "request_with_retries", side_effect=lambda method, url, **kw: response(graph()) if "/choreography/" in url else response([None])):
            self.assertEqual(self.start().status_code, 502)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").status_code, 409)
        self.start()
        self.assertEqual(self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "missing"}).status_code, 404)
        self.assertEqual(self.client.put(f"/choreography/{CHOREO}/run/state", json={"state_id": "99999999"}).status_code, 404)
        self.assertEqual(self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "go"}).status_code, 200)

    def test_unavailable_target_keeps_state(self):
        self.start()
        def upstream(method, url, **kwargs):
            if url.endswith(f"/exercise/{SECOND}/frames"):
                raise requests.ConnectionError("exercise service down")
            return response({"repetitions": 1})
        self.calls.clear()
        with patch.object(translator, "request_with_retries", side_effect=upstream):
            result = self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "go"})
        self.assertEqual(result.status_code, 502)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").json["state_id"], FIRST)

    def test_partial_robot_failure_keeps_source_state(self):
        self.start()
        self.calls.clear()
        with patch.object(translator, "call_nao_set_pose", side_effect=requests.Timeout("robot")):
            failed = self.client.post(f"/choreography/{CHOREO}/run/signal", json={"transition_id": "go"})
        self.assertEqual(failed.status_code, 502)
        self.assertTrue(failed.json["partial_playback"])
        self.assertEqual(failed.json["state"]["state_id"], FIRST)
        self.assertEqual(self.calls, [("voice", {"text": SECOND})])
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").json["state_id"], FIRST)
        translator._runs.clear()
        with patch.object(translator, "call_nao_set_pose", return_value={"success": False}):
            self.assertEqual(self.start().status_code, 502)
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").status_code, 409)

    def test_conflicting_request_is_rejected_while_playback_is_running(self):
        entered = threading.Event()
        release = threading.Event()
        outcomes = []

        def slow_pose(angles):
            entered.set()
            release.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_set_pose", side_effect=slow_pose):
            worker = threading.Thread(target=lambda: outcomes.append(translator.app.test_client().post(f"/choreography/{CHOREO}/run").status_code))
            worker.start()
            self.assertTrue(entered.wait(3))
            try:
                self.assertEqual(self.start().status_code, 409)
                self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").status_code, 409)
            finally:
                release.set()
                worker.join(3)
        self.assertEqual(outcomes, [200])
        self.assertEqual(translator._run_locks, {})

    def test_different_ids_cannot_play_on_robot_concurrently(self):
        entered = threading.Event()
        release = threading.Event()
        outcomes = []

        def pose(angles):
            if threading.current_thread().name == "first-run":
                entered.set()
                release.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_set_pose", side_effect=pose):
            worker = threading.Thread(name="first-run", target=lambda: outcomes.append(translator.app.test_client().post(f"/choreography/{CHOREO}/run").status_code))
            worker.start()
            self.assertTrue(entered.wait(3))
            try:
                self.assertEqual(self.start(OTHER).status_code, 409)
                self.assertEqual(self.client.get(f"/choreography/{OTHER}/run").status_code, 409)
                self.assertEqual(self.calls, [("voice", {"text": FIRST})])
            finally:
                release.set()
                worker.join(3)
        self.assertEqual(outcomes, [200])
        self.assertEqual(self.start(OTHER).status_code, 200)
        self.assertEqual(self.client.get(f"/choreography/{CHOREO}/run").json["state_id"], FIRST)
        self.assertEqual(self.client.get(f"/choreography/{OTHER}/run").json["state_id"], FIRST)

    def test_legacy_run_waits_for_choreography_playback(self):
        entered = threading.Event()
        release = threading.Event()
        legacy_started = threading.Event()
        outcomes = []

        def pose(angles):
            if threading.current_thread().name == "first-run":
                entered.set()
                release.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_set_pose", side_effect=pose):
            first = threading.Thread(name="first-run", target=lambda: outcomes.append(translator.app.test_client().post(f"/choreography/{CHOREO}/run").status_code))
            def legacy_run():
                legacy_started.set()
                outcomes.append(translator.app.test_client().post(f"/exercise/{SECOND}/run", json={"repetitions": 1}).status_code)
            second = threading.Thread(name="legacy-run", target=legacy_run)
            first.start()
            self.assertTrue(entered.wait(3))
            second.start()
            try:
                self.assertTrue(legacy_started.wait(3))
                self.assertEqual(len(outcomes), 0)
            finally:
                release.set()
                first.join(3)
                second.join(3)
        self.assertEqual(outcomes, [200, 200])
        self.assertEqual(translator._run_locks, {})

    def test_unknown_ids_do_not_leave_process_locks(self):
        for index in range(100):
            self.assertEqual(self.client.get(f"/choreography/{index:08x}/run").status_code, 409)
        self.assertEqual(translator._run_locks, {})
