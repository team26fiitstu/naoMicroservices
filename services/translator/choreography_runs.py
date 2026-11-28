"""Threaded choreography runs and robot access coordination."""

import re
import threading
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ChoreographyRun:
    run_id: str
    choreography_id: str
    graph: dict
    state_id: str
    status: str = "performing"
    source_state_id: str | None = None
    playback: dict | None = None
    error: str | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    worker_done: threading.Event = field(default_factory=threading.Event)
    reservation_lock: threading.Lock = field(default_factory=threading.Lock)
    retained: bool = False
    reservation_released: bool = False


class ChoreographyRuns:
    MAX_STOPPED_RUNS = 50
    # Must remain at least as long as naoRobotAPI's RESERVATION_SECONDS.
    RESERVATION_UNCERTAINTY_SECONDS = 120
    _choreography_id_re = re.compile(r"^[0-9a-f]{8}$")

    def __init__(self, load_graph, reserve, release, play, logger):
        self.load_graph = load_graph
        self.reserve = reserve
        self.release = release
        self.play = play
        self.logger = logger
        self._runs = {}
        self._stopped_run_ids = []
        self._current_run_id = None
        self._starting = False
        self._reservation_uncertain_until = 0
        self._run_registry_lock = threading.Lock()
        self.standalone_lock = threading.Lock()

    def claim_standalone(self):
        with self._run_registry_lock:
            if self._reservation_uncertain():
                return False, "robot reservation may still be active"
            if self._starting or self._current_run_id is not None or self.standalone_lock.locked():
                return False, "robot is busy with playback"
            return self.standalone_lock.acquire(blocking=False), "robot is busy with playback"

    def _reservation_uncertain(self):
        """Called under the registry lock; expire the local guard lazily."""
        if time.monotonic() < self._reservation_uncertain_until:
            return True
        self._reservation_uncertain_until = 0
        return False

    def _mark_reservation_uncertain(self):
        """Keep new playback out until a possibly live remote lease expires."""
        self._reservation_uncertain_until = max(
            self._reservation_uncertain_until,
            time.monotonic() + self.RESERVATION_UNCERTAINTY_SECONDS,
        )

    def _snapshot(self, run):
        state_id = run.state_id
        return {"run_id": run.run_id, "choreography_id": run.choreography_id,
                "state_id": state_id, "status": run.status,
                "outgoing_transitions": [dict(t) for t in run.graph["transitions"]
                                         if t["from"] == state_id],
                "playback": run.playback, "error": run.error}

    def _retain_stopped_run(self, run):
        """Keep a bounded history for GET /run/<run_id> after completion."""
        if run.retained:
            return
        run.retained = True
        self._stopped_run_ids.append(run.run_id)
        if len(self._stopped_run_ids) > self.MAX_STOPPED_RUNS:
            self._runs.pop(self._stopped_run_ids.pop(0), None)

    def _take_reservation_release(self, run):
        if run.reservation_released:
            return None
        run.reservation_released = True
        return run.run_id

    def _renew_run_reservation(self, run):
        # Stop must not release the lease before an in-flight renewal completes.
        with run.reservation_lock:
            if run.stop_event.is_set():
                return None
            return self.reserve(run.run_id)

    def _release_run_reservation(self, run):
        with run.reservation_lock:
            return self.release(run.run_id)

    def _renew_robot_reservation(self, run):
        while not run.stop_event.wait(20):
            failure = self._renew_run_reservation(run)
            if failure is None:
                continue
            token_to_release = None
            with self._run_registry_lock:
                if run.status == "stopped":
                    return
                run.error = "robot reservation was lost"
                run.stop_event.set()
                run.status = "stopped"
                if run.worker_done.is_set():
                    token_to_release = self._take_reservation_release(run)
            if token_to_release:
                released = self._release_run_reservation(run)
                with self._run_registry_lock:
                    if not released:
                        run.error += "; failed to release robot reservation"
                        self._mark_reservation_uncertain()
                    if self._current_run_id == run.run_id:
                        self._current_run_id = None
                    self._retain_stopped_run(run)
            return

    def _perform_state(self, run, target, starting):
        try:
            # state holds its own id, robot plays exercise behind it, bad graph ends as playback error
            exercise_id = next(s["exercise_id"] for s in run.graph["states"] if s["id"] == target)
            result, failure = self.play(run.run_id, exercise_id, run.stop_event.is_set)
        except Exception:
            self.logger.exception("choreography playback failed for run %s", run.run_id)
            result, failure = None, ({"error": "unexpected playback failure"}, 502)
        token_to_release = None
        with self._run_registry_lock:
            run.playback = result
            if failure:
                playback_error = failure[0]["error"]
            elif result is not None and any(item["status"] == "error" for item in result["results"]):
                playback_error = "robot playback failed; some commands may have completed"
            else:
                playback_error = None
            if run.error:
                if playback_error:
                    run.error += "; " + playback_error
            else:
                run.error = playback_error
            if run.error and not starting:
                run.state_id = run.source_state_id
            if run.stop_event.is_set():
                run.status = "stopped"
            elif run.error:
                run.status = "stopped" if starting else "waiting"
            else:
                run.status = "waiting"
            run.source_state_id = None
            if run.status == "stopped":
                run.stop_event.set()
                token_to_release = self._take_reservation_release(run)
            else:
                run.worker_done.set()
        if token_to_release:
            released = self._release_run_reservation(run)
        if token_to_release:
            with self._run_registry_lock:
                if not released:
                    release_error = "failed to release robot reservation; it will expire automatically"
                    run.error = run.error + "; " + release_error if run.error else release_error
                    self._mark_reservation_uncertain()
                run.worker_done.set()
                if self._current_run_id == run.run_id:
                    self._current_run_id = None
                self._retain_stopped_run(run)

    def _start_performance(self, run, target, starting=False):
        previous = (run.source_state_id, run.state_id, run.status,
                    run.error, run.worker_done.is_set())
        run.source_state_id = None if starting else run.state_id
        run.state_id = target
        run.status = "performing"
        run.error = None
        run.worker_done.clear()
        try:
            worker = threading.Thread(target=self._perform_state, args=(run, target, starting), daemon=True)
            worker.start()
        except RuntimeError:
            run.source_state_id, run.state_id, run.status, run.error, was_done = previous
            if was_done:
                run.worker_done.set()
            raise

    def start_choreography_run(self, choreography_id):
        if not self._choreography_id_re.fullmatch(choreography_id):
            return {"error": "choreography_id must be an 8-character lowercase hex ID"}, 400
        with self._run_registry_lock:
            if self._reservation_uncertain():
                return {"error": "robot reservation may still be active"}, 409
            if self._current_run_id is not None or self._starting or self.standalone_lock.locked():
                return {"error": "another choreography run is active"}, 409
            self._starting = True
        try:
            graph, failure = self.load_graph(choreography_id)
            if failure:
                return failure
            run_id = uuid.uuid4().hex
            failure = self.reserve(run_id)
            if failure:
                if failure[1] == 502:
                    # A lost POST response does not prove the robot rejected the lease.
                    # DELETE retires this token even when the POST arrives later.
                    if not self.release(run_id):
                        self.logger.error("could not retire uncertain reservation for run %s", run_id)
                        with self._run_registry_lock:
                            self._mark_reservation_uncertain()
                return failure
            worker_error = None
            with self._run_registry_lock:
                run = ChoreographyRun(run_id, choreography_id, graph, graph["initial_state"])
                self._runs[run_id] = run
                self._current_run_id = run_id
                try:
                    self._start_performance(run, graph["initial_state"], starting=True)
                except RuntimeError as exc:
                    self._runs.pop(run_id)
                    self._current_run_id = None
                    worker_error = str(exc)
                else:
                    try:
                        threading.Thread(target=self._renew_robot_reservation, args=(run,), daemon=True).start()
                    except RuntimeError as exc:
                        run.stop_event.set()
                        run.status = "stopped"
                        run.error = "failed to start reservation monitor: " + str(exc)
                        return self._snapshot(run), 503
                    return self._snapshot(run), 202
            released = self.release(run_id)
            error = {"error": "failed to start playback worker", "detail": worker_error}
            if not released:
                error["cleanup_error"] = "robot reservation may remain until it expires"
                with self._run_registry_lock:
                    self._mark_reservation_uncertain()
            return error, 503
        finally:
            with self._run_registry_lock:
                self._starting = False

    def current_choreography_run(self):
        with self._run_registry_lock:
            if self._current_run_id is None or self._runs[self._current_run_id].status == "stopped":
                return {"error": "no active choreography run"}, 404
            return self._snapshot(self._runs[self._current_run_id]), 200

    def get_choreography_run(self, run_id):
        with self._run_registry_lock:
            run = self._runs.get(run_id)
            return (self._snapshot(run), 200) if run else ({"error": "run not found"}, 404)

    def signal_choreography_run(self, run_id, transition_id):
        with self._run_registry_lock:
            run = self._runs.get(run_id)
            if run is None:
                return {"error": "run not found"}, 404
            if run.status != "waiting":
                return {"error": "run must be waiting for a signal"}, 409
            transition = next((t for t in run.graph["transitions"] if t["id"] == transition_id), None)
            if transition is None:
                return {"error": f"Transition '{transition_id}' not found in this run"}, 409
            if transition["from"] != run.state_id:
                return {"error": "transition does not start at current state"}, 409
            try:
                self._start_performance(run, transition["to"])
            except RuntimeError as exc:
                return {"error": "failed to start playback worker", "detail": str(exc)}, 503
            return self._snapshot(run), 202

    def goto_choreography_state(self, run_id, state_id):
        with self._run_registry_lock:
            run = self._runs.get(run_id)
            if run is None:
                return {"error": "run not found"}, 404
            if run.status != "waiting":
                return {"error": "run must be waiting before goto"}, 409
            if state_id not in {s["id"] for s in run.graph["states"]}:
                return {"error": f"State '{state_id}' not found"}, 404
            run.state_id = state_id
            run.playback = None
            run.error = None
            return self._snapshot(run), 200

    def stop_choreography_run(self, run_id):
        token_to_release = None
        with self._run_registry_lock:
            run = self._runs.get(run_id)
            if run is None:
                return {"error": "run not found"}, 404
            if run.status == "stopped":
                return {"error": "run already stopped"}, 409
            run.stop_event.set()
            run.status = "stopped"
            # Keep the robot reserved until an in-flight command finishes.
            if run.worker_done.is_set():
                token_to_release = self._take_reservation_release(run)
        if token_to_release:
            released = self._release_run_reservation(run)
            with self._run_registry_lock:
                if not released:
                    release_error = "failed to release robot reservation; it will expire automatically"
                    run.error = run.error + "; " + release_error if run.error else release_error
                    self._mark_reservation_uncertain()
                if self._current_run_id == run.run_id:
                    self._current_run_id = None
                self._retain_stopped_run(run)
        with self._run_registry_lock:
            return self._snapshot(run), 200
