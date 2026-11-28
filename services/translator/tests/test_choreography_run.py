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
real_reserve_robot_for_run = translator.reserve_robot_for_run
real_release_robot_reservation = translator.release_robot_reservation

CHOREO = "aaaaaaaa"
OTHER = "bbbbbbbb"
FIRST = "11111111"
SECOND = "22222222"
FIRST_STATE = "state-one"
SECOND_STATE = "state-two"


def graph(choreography_id=CHOREO):
    return {"schema_version": 1, "id": choreography_id, "initial_state": FIRST_STATE,
            "states": [{"id": FIRST_STATE, "exercise_id": FIRST},
                       {"id": SECOND_STATE, "exercise_id": SECOND}],
            "transitions": [{"id": "go", "from": FIRST_STATE, "to": SECOND_STATE, "label": "go"},
                            {"id": "back", "from": SECOND_STATE, "to": FIRST_STATE, "label": "back"}]}


class ChoreographyRun(OfflineCase):
    def setUp(self):
        super().setUp()
        with translator.choreography_runs._run_registry_lock:
            translator.choreography_runs._runs.clear()
            translator.choreography_runs._stopped_run_ids.clear()
            translator.choreography_runs._current_run_id = None
            translator.choreography_runs._starting = False
            translator.choreography_runs._reservation_uncertain_until = 0
        self.client = translator.app.test_client()
        self.calls = []
        self.reserve = patch.object(translator, "reserve_robot_for_run", return_value=None)
        self.release_reservation = patch.object(translator, "release_robot_reservation", return_value=True)
        self.reserve_call = self.reserve.start()
        self.release_call = self.release_reservation.start()
        self.addCleanup(self.reserve.stop)
        self.addCleanup(self.release_reservation.stop)

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

    def tearDown(self):
        for run in list(translator.choreography_runs._runs.values()):
            self.assertTrue(run.worker_done.wait(3), "playback worker did not finish")
            run.stop_event.set()  # end the fake lease renewal thread
        super().tearDown()

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
        self.assertEqual(run["state_id"], FIRST_STATE)
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
        self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "missing"}).status_code, 409)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.get(f"/run/{self.run_id}").json["state_id"], FIRST_STATE)
        direct = self.client.post(f"/run/{self.run_id}/goto", json={"state_id": SECOND_STATE})
        self.assertEqual((direct.status_code, direct.json["state_id"]), (200, SECOND_STATE))
        self.assertEqual(direct.json["status"], "waiting")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"}).status_code, 409)
        accepted = self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "back"})
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(accepted.json["state_id"], FIRST_STATE)
        self.assertEqual(self.wait_status(self.run_id, "waiting")["state_id"], FIRST_STATE)
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
        self.release_call.assert_called_once()
        self.assertEqual(self.start(OTHER).status_code, 202)
        self.wait_status(self.run_id, "waiting")

    def test_standalone_exercise_is_rejected_during_performance_and_waiting(self):
        entered = threading.Event()
        resume = threading.Event()

        def slow_pose(angles):
            entered.set()
            resume.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_set_pose", side_effect=slow_pose):
            self.assertEqual(self.start().status_code, 202)
            try:
                self.assertTrue(entered.wait(3))
                with patch.object(translator, "fetch_exercise") as fetch:
                    self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 409)
                    fetch.assert_not_called()
            finally:
                resume.set()
            self.wait_status(self.run_id, "waiting")
        with patch.object(translator, "fetch_exercise") as fetch:
            self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 409)
            fetch.assert_not_called()

    def test_standalone_exercise_is_rejected_while_reservation_is_being_released(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        releasing = threading.Event()
        finish_release = threading.Event()
        stop_results = []

        def slow_release(run_id):
            releasing.set()
            self.assertTrue(finish_release.wait(3))
            return True

        def stop():
            stop_results.append(translator.app.test_client().post(f"/run/{self.run_id}/stop").status_code)

        self.release_call.side_effect = slow_release
        stop_thread = threading.Thread(target=stop)
        stop_thread.start()
        try:
            self.assertTrue(releasing.wait(3))
            with patch.object(translator, "fetch_exercise") as fetch:
                self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 409)
                fetch.assert_not_called()
            self.assertEqual(self.start(OTHER).status_code, 409)
        finally:
            finish_release.set()
            stop_thread.join(3)

        self.assertFalse(stop_thread.is_alive())
        self.assertEqual(stop_results, [200])
        self.assertEqual(self.start(OTHER).status_code, 202)
        self.wait_status(self.run_id, "waiting")

    def test_reservation_loss_keeps_standalone_blocked_until_release_finishes(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        run = translator.choreography_runs._runs[self.run_id]
        releasing = threading.Event()
        finish_release = threading.Event()

        def slow_release(run_id):
            releasing.set()
            self.assertTrue(finish_release.wait(3))
            return True

        self.reserve_call.return_value = ({"error": "reservation lost"}, 502)
        self.release_call.side_effect = slow_release
        with patch.object(run.stop_event, "wait", return_value=False):
            renew_thread = threading.Thread(target=translator.choreography_runs._renew_robot_reservation, args=(run,))
            renew_thread.start()
            try:
                self.assertTrue(releasing.wait(3))
                with patch.object(translator, "fetch_exercise") as fetch:
                    self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 409)
                    fetch.assert_not_called()
                self.assertEqual(self.start(OTHER).status_code, 409)
            finally:
                finish_release.set()
                renew_thread.join(3)

        self.assertFalse(renew_thread.is_alive())
        self.assertEqual(self.client.get(f"/run/{self.run_id}").json["error"], "robot reservation was lost")
        self.reserve_call.return_value = None
        self.assertEqual(self.start(OTHER).status_code, 202)
        self.wait_status(self.run_id, "waiting")

    def test_robot_reservation_failure_does_not_create_run(self):
        for status in (409, 502):
            with self.subTest(status=status), patch.object(
                translator, "reserve_robot_for_run",
                side_effect=lambda run_id: ({"error": "robot unavailable"}, status),
            ):
                self.assertEqual(self.start().status_code, status)
                self.assertEqual(self.client.get("/run/current").status_code, 404)
                self.assertEqual(translator.choreography_runs._runs, {})
                self.assertEqual(self.release_call.call_count, 0 if status == 409 else 1)

    def test_lost_initial_reservation_reply_releases_remote_lease(self):
        remote = {"token": None, "retired": set()}
        calls = []

        def upstream(method, url, **kwargs):
            if "/choreography/" in url:
                return response(graph())
            self.assertEqual(url, translator.ROBOT_RESERVATION_URL)
            token = kwargs["json"]["token"]
            calls.append((method, token))
            if method == "POST":
                remote["token"] = token
                raise requests.ReadTimeout("reservation reply lost")
            remote["retired"].add(token)
            remote["token"] = None
            return response({"success": True})

        with patch.object(translator, "request_with_retries", side_effect=upstream), \
                patch.object(translator, "reserve_robot_for_run", wraps=real_reserve_robot_for_run), \
                patch.object(translator, "release_robot_reservation", wraps=real_release_robot_reservation):
            result = self.start()

        self.assertEqual(result.status_code, 502)
        self.assertEqual([method for method, _ in calls], ["POST", "DELETE"])
        self.assertEqual(calls[0][1], calls[1][1])
        self.assertIsNone(remote["token"])
        self.assertIn(calls[0][1], remote["retired"])
        self.assertEqual(self.client.get("/run/current").status_code, 404)
        self.assertEqual(translator.choreography_runs._runs, {})

    def test_worker_start_failure_releases_reservation(self):
        with patch.object(translator.threading.Thread, "start", side_effect=RuntimeError("no threads")):
            result = self.start()
        self.assertEqual(result.status_code, 503)
        self.assertIn("failed to start playback worker", result.json["error"])
        self.assertEqual(translator.choreography_runs._runs, {})
        self.assertEqual(self.client.get("/run/current").status_code, 404)
        self.release_call.assert_called_once()

    def test_signal_worker_start_failure_restores_waiting_state(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        self.calls.clear()
        with patch.object(translator.threading.Thread, "start", side_effect=RuntimeError("no threads")):
            result = self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"})
        self.assertEqual(result.status_code, 503)
        current = self.client.get(f"/run/{self.run_id}").json
        self.assertEqual((current["state_id"], current["status"]), (FIRST_STATE, "waiting"))
        self.assertTrue(translator.choreography_runs._runs[self.run_id].worker_done.is_set())
        self.assertEqual(self.calls, [])
        self.release_call.assert_not_called()

    def test_reservation_monitor_start_failure_stops_worker(self):
        original_start = threading.Thread.start
        starts = []

        def fail_second_start(thread):
            starts.append(thread)
            if len(starts) == 2:
                raise RuntimeError("no monitor thread")
            return original_start(thread)

        with patch.object(translator.threading.Thread, "start", fail_second_start):
            result = self.start()
        self.assertEqual(result.status_code, 503)
        self.assertIn("failed to start reservation monitor", result.json["error"])
        run_id = result.json["run_id"]
        self.assertTrue(translator.choreography_runs._runs[run_id].worker_done.wait(3))
        self.assertEqual(self.client.get(f"/run/{run_id}").json["status"], "stopped")
        self.assertEqual(self.client.get("/run/current").status_code, 404)
        self.release_call.assert_called_once()

    def test_invalid_unknown_empty_and_unavailable(self):
        self.assertEqual(self.start("bad").status_code, 400)
        with patch.object(translator, "request_with_retries", return_value=response({}, 404)):
            self.assertEqual(self.start().status_code, 404)
        with patch.object(translator, "request_with_retries", side_effect=requests.ConnectionError("down")):
            self.assertEqual(self.start().status_code, 502)
        with patch.object(translator, "request_with_retries", return_value=response(dict(graph(), states=None))):
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
        self.assertEqual(run["state_id"], FIRST_STATE)
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
        self.assertEqual(run["state_id"], FIRST_STATE)
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
            self.assertEqual(self.client.post(f"/run/{self.run_id}/goto", json={"state_id": SECOND_STATE}).status_code, 409)
            self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 200)
            self.assertEqual(self.start(OTHER).status_code, 409)
            release.set()
            self.wait_status(self.run_id, "stopped")
        self.assertEqual(commands, [[1]])
        self.assertEqual(self.client.get("/run/current").status_code, 404)

    def test_stop_finishes_current_frame_before_stopping(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_speech(lines):
            self.calls.append(("voice", lines))
            entered.set()
            release.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_voice_lines", side_effect=slow_speech):
            self.start()
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 200)
            release.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not translator.choreography_runs._runs[self.run_id].worker_done.is_set():
                time.sleep(0.005)
        self.assertEqual(self.calls, [("voice", {"text": FIRST}), ("pose", [1])])

    def test_stop_preserves_in_flight_robot_error(self):
        entered = threading.Event()
        release = threading.Event()

        def failed_pose(angles):
            entered.set()
            release.wait(3)
            raise requests.Timeout("robot timeout after stop")

        with patch.object(translator, "call_nao_set_pose", side_effect=failed_pose):
            self.start()
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 200)
            release.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not translator.choreography_runs._runs[self.run_id].worker_done.is_set():
                time.sleep(0.005)
        result = self.client.get(f"/run/{self.run_id}").json
        self.assertEqual(result["status"], "stopped")
        self.assertIn("robot playback failed", result["error"])
        self.assertEqual(result["playback"]["results"][-1]["status"], "error")

    def test_stopped_run_history_is_bounded(self):
        run_ids = []
        with patch.object(translator.choreography_runs, "MAX_STOPPED_RUNS", 2):
            for _ in range(3):
                self.start()
                self.wait_status(self.run_id, "waiting")
                run_ids.append(self.run_id)
                self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 200)
        self.assertEqual(self.client.get(f"/run/{run_ids[0]}").status_code, 404)
        self.assertEqual([self.client.get(f"/run/{run_id}").status_code for run_id in run_ids[1:]], [200, 200])
        self.assertEqual(len(translator.choreography_runs._runs), 2)

    def test_failed_reservation_release_is_visible(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        self.calls.clear()
        self.release_call.return_value = False
        stopped = self.client.post(f"/run/{self.run_id}/stop")
        self.assertEqual(stopped.status_code, 200)
        self.assertEqual(stopped.json["status"], "stopped")
        self.assertIn("failed to release robot reservation", stopped.json["error"])
        self.assertEqual(self.client.get("/run/current").status_code, 404)
        with patch.object(translator, "fetch_exercise") as fetch:
            self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 409)
            fetch.assert_not_called()
        self.assertEqual(self.start(OTHER).status_code, 409)
        self.assertEqual(self.calls, [])

        deadline = translator.choreography_runs._reservation_uncertain_until
        with patch("choreography_runs.time.monotonic", return_value=deadline + 1):
            self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 200)
        self.assertEqual(translator.choreography_runs._reservation_uncertain_until, 0)

    def test_uncertain_initial_reservation_blocks_new_playback(self):
        self.reserve_call.return_value = ({"error": "robot unavailable"}, 502)
        self.release_call.return_value = False
        self.assertEqual(self.start().status_code, 502)
        with patch.object(translator, "fetch_exercise") as fetch:
            self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 409)
            fetch.assert_not_called()
        self.assertEqual(self.start(OTHER).status_code, 409)

    def test_failed_release_after_playback_error_blocks_new_playback(self):
        self.release_call.return_value = False
        with patch.object(translator, "request_with_retries", side_effect=lambda method, url, **kw:
                          response(graph()) if "/choreography/" in url else response([])):
            self.assertEqual(self.start().status_code, 202)
            run = self.wait_status(self.run_id, "stopped")
        self.assertTrue(translator.choreography_runs._runs[self.run_id].worker_done.wait(3))
        self.assertIn("failed to release robot reservation", self.client.get(f"/run/{self.run_id}").json["error"])
        self.assertIn("no frames", run["error"])
        with patch.object(translator, "fetch_exercise") as fetch:
            self.assertEqual(self.client.post(f"/exercise/{FIRST}/run").status_code, 409)
            fetch.assert_not_called()

    def test_stop_waits_for_in_flight_reservation_renewal(self):
        self.start()
        self.wait_status(self.run_id, "waiting")
        run = translator.choreography_runs._runs[self.run_id]
        remote = {"token": self.run_id}
        renewing = threading.Event()
        finish_renewal = threading.Event()
        stop_finished = threading.Event()
        stop_status = []

        def slow_renew(run_id):
            renewing.set()
            self.assertTrue(finish_renewal.wait(3))
            remote["token"] = run_id
            return None

        def release(run_id):
            self.assertEqual(remote["token"], run_id)
            remote["token"] = None
            return True

        def stop():
            stop_status.append(translator.app.test_client().post(f"/run/{self.run_id}/stop").status_code)
            stop_finished.set()

        self.reserve_call.side_effect = slow_renew
        self.release_call.side_effect = release
        renew_thread = threading.Thread(target=translator.choreography_runs._renew_run_reservation, args=(run,))
        stop_thread = threading.Thread(target=stop)
        renew_thread.start()
        try:
            self.assertTrue(renewing.wait(3))
            stop_thread.start()
            self.assertTrue(run.stop_event.wait(3))
            self.assertFalse(stop_finished.is_set())
        finally:
            finish_renewal.set()
            renew_thread.join(3)
            if stop_thread.ident is not None:
                stop_thread.join(3)

        self.assertEqual(stop_status, [200])
        self.assertIsNone(remote["token"])
        renew_count = self.reserve_call.call_count
        self.assertIsNone(translator.choreography_runs._renew_run_reservation(run))
        self.assertEqual(self.reserve_call.call_count, renew_count)

    def test_reservation_loss_during_playback_remains_reported(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_pose(angles):
            entered.set()
            release.wait(3)
            return {"success": True}

        with patch.object(translator, "call_nao_set_pose", side_effect=slow_pose):
            self.start()
            self.assertTrue(entered.wait(3))
            with translator.choreography_runs._run_registry_lock:
                run = translator.choreography_runs._runs[self.run_id]
                run.error = "robot reservation was lost"
                run.stop_event.set()
                run.status = "stopped"
            release.set()
            self.assertTrue(run.worker_done.wait(3))
        current = self.client.get(f"/run/{self.run_id}").json
        self.assertEqual(current["status"], "stopped")
        self.assertEqual(current["error"], "robot reservation was lost")

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
            accepted = self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"})
            self.assertEqual(accepted.status_code, 202)
            self.assertEqual((accepted.json["state_id"], accepted.json["status"]), (SECOND_STATE, "performing"))
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.client.post(f"/run/{self.run_id}/stop").status_code, 200)
            self.assertEqual(self.start(OTHER).status_code, 409)
            release.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and translator.choreography_runs._current_run_id is not None:
            time.sleep(0.005)
        self.assertIsNone(translator.choreography_runs._current_run_id)

    def test_voice_only_and_pose_only_states(self):
        def upstream(method, url, **kwargs):
            if "/choreography/" in url:
                return response(graph())
            if url.endswith(f"/exercise/{FIRST}/frames"):
                return response([{"frame_index": 0, "voice_lines": {"text": "hello"}, "nao_angles": []}])
            if url.endswith(f"/exercise/{SECOND}/frames"):
                return response([{"frame_index": 0, "nao_angles": [1]}])
            return response({"repetitions": 1})

        with patch.object(translator, "request_with_retries", side_effect=upstream):
            self.start()
            self.wait_status(self.run_id, "waiting")
            self.assertEqual(self.calls, [("voice", {"text": "hello"})])
            self.assertEqual(self.client.post(f"/run/{self.run_id}/signal", json={"transition_id": "go"}).status_code, 202)
            self.wait_status(self.run_id, "waiting")
        self.assertEqual(self.calls, [("voice", {"text": "hello"}), ("pose", [1])])

    def test_frame_without_voice_or_pose_is_empty(self):
        with patch.object(translator, "request_with_retries", side_effect=lambda method, url, **kw: response(graph()) if "/choreography/" in url else response([{"frame_index": 0, "nao_angles": []}])):
            self.start()
            self.assertIn("no playable content", self.wait_status(self.run_id, "stopped")["error"])
        self.assertEqual(self.calls, [])

    def test_legacy_exercise_contract(self):
        result = self.client.post(f"/exercise/{FIRST}/run", json={"repetitions": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["total_poses_sent"], 3)
