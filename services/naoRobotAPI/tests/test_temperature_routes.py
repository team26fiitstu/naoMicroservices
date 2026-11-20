"""Offline tests for joint temperature reading and logging in naoRobotAPI."""
import csv
import io
import shutil
import sys
import tempfile
import time
import types

from flask import Flask

from tests._support import OfflineCase, ROOT

# NAOqi is unavailable offline; the robot package imports it at module level.
naoqi_stub = sys.modules.setdefault("naoqi", types.ModuleType("naoqi"))
if not hasattr(naoqi_stub, "ALProxy"):
    naoqi_stub.ALProxy = lambda *args: (_ for _ in ()).throw(AssertionError("real NAOqi proxy requested"))
ROBOT_DIR = ROOT / "services/naoRobotAPI"
if str(ROBOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROBOT_DIR))

from robot.temperature import temperature, temperature_api  # noqa: E402

JOINTS = ("RShoulderPitch", "LShoulderPitch", "HeadYaw", "LHand")


def wait_until(condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


class ScriptedSensors(object):
    """Fake NaoSensors: RShoulderPitch heats fastest and is flagged hot from read 2."""

    connect_error = None
    fail_reads = ()

    def __init__(self):
        if ScriptedSensors.connect_error:
            raise RuntimeError(ScriptedSensors.connect_error)
        self.reads = 0

    def read(self):
        index = self.reads
        self.reads += 1
        if index in ScriptedSensors.fail_reads:
            raise RuntimeError("fake read failure")
        return {
            "RShoulderPitch": {"temperature_c": 30.0 + 2 * index, "status": 1.0 if index >= 2 else 0.0,
                               "position_rad": -1.4, "current_a": 0.8},
            "LShoulderPitch": {"temperature_c": 30.0 + index, "status": 0.0,
                               "position_rad": -1.3, "current_a": -0.4},
            "HeadYaw": {"temperature_c": 30.0, "status": 0.0, "position_rad": 0.0, "current_a": 0.0},
            "LHand": {"temperature_c": None, "status": None, "position_rad": None, "current_a": None},
        }


class FakeMemory(object):
    def __init__(self, values, list_data_fails=False):
        self.values = values
        self.list_data_fails = list_data_fails
        self.calls = []

    def getListData(self, keys):
        self.calls.append("getListData")
        if self.list_data_fails:
            raise RuntimeError("getListData failed")
        return [self.values.get(key) for key in keys]

    def getData(self, key):
        self.calls.append("getData")
        if key not in self.values:
            raise RuntimeError("key not found: %s" % key)
        return self.values[key]


class FakeMotion(object):
    def __init__(self):
        self.calls = []

    def getBodyNames(self, chain):
        self.calls.append(("getBodyNames", chain))
        return ["HeadYaw", "RShoulderPitch"]


class NaoSensorsTests(OfflineCase):
    def make_sensors(self, memory):
        motion = FakeMotion()
        proxies = {"ALMemory": memory, "ALMotion": motion}
        requested = []

        def factory(name, ip, port):
            requested.append(name)
            return proxies[name]

        sensors = temperature.NaoSensors(proxy_factory=factory)
        return sensors, motion, requested

    def test_reads_all_joint_sensors_in_one_call(self):
        base = "Device/SubDeviceList/%s/"
        values = {}
        for joint, temp in (("HeadYaw", 41.0), ("RShoulderPitch", 55)):
            values[base % joint + "Temperature/Sensor/Value"] = temp
            values[base % joint + "Temperature/Sensor/Status"] = 1
            values[base % joint + "Position/Sensor/Value"] = 0.25
            values[base % joint + "ElectricCurrent/Sensor/Value"] = "n/a"
        memory = FakeMemory(values)
        sensors, motion, requested = self.make_sensors(memory)
        result = sensors.read()
        self.assertEqual(sorted(requested), ["ALMemory", "ALMotion"])
        self.assertEqual(motion.calls, [("getBodyNames", "Body")])
        self.assertEqual(memory.calls, ["getListData"])
        self.assertEqual(len(sensors.keys), 8)
        self.assertEqual(result["RShoulderPitch"], {
            "temperature_c": 55.0, "status": 1.0, "position_rad": 0.25, "current_a": None,
        })
        self.assertEqual(result["HeadYaw"]["temperature_c"], 41.0)

    def test_falls_back_to_single_reads_and_tolerates_missing_keys(self):
        # Choregraphe's virtual robot may not provide temperature keys.
        values = {"Device/SubDeviceList/HeadYaw/Position/Sensor/Value": 0.5}
        memory = FakeMemory(values, list_data_fails=True)
        sensors, _, _ = self.make_sensors(memory)
        result = sensors.read()
        self.assertEqual(memory.calls[0], "getListData")
        self.assertEqual(memory.calls.count("getData"), 8)
        self.assertEqual(result["HeadYaw"], {
            "temperature_c": None, "status": None, "position_rad": 0.5, "current_a": None,
        })
        self.assertEqual(set(result["RShoulderPitch"].values()), {None})


class TemperatureRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        ScriptedSensors.connect_error = None
        ScriptedSensors.fail_reads = ()
        self.log_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.log_dir, True)
        self.logger = temperature.TemperatureLogger(self.log_dir, sensors_factory=ScriptedSensors)
        self.previous_logger = temperature_api._logger
        temperature_api._logger = self.logger
        self.addCleanup(setattr, temperature_api, "_logger", self.previous_logger)
        self.addCleanup(self.stop_if_running)
        app = Flask(__name__)
        app.register_blueprint(temperature_api.temperature_api, url_prefix="/temperature")
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def stop_if_running(self):
        if self.logger.active():
            self.logger.stop()

    def test_snapshot(self):
        result = self.client.get("/temperature")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(sorted(result.json["joints"]), sorted(JOINTS))
        self.assertEqual(result.json["joints"]["RShoulderPitch"]["temperature_c"], 30.0)
        self.assertTrue(result.json["timestamp"].endswith("Z"))

    def test_robot_unavailable(self):
        ScriptedSensors.connect_error = "connection refused"
        self.assertEqual(self.client.get("/temperature").status_code, 503)
        result = self.client.post("/temperature/log/start", json={})
        self.assertEqual(result.status_code, 503)
        self.assertIn("connection refused", result.json["detail"])
        self.assertIsNone(self.client.get("/temperature/log/active").json["active"])

    def test_start_validation(self):
        bad_bodies = (
            {"interval_s": 0.1}, {"interval_s": 61}, {"interval_s": "1"}, {"interval_s": True},
            {"max_duration_s": 0}, {"max_duration_s": 5 * 3600},
            {"label": ""}, {"label": "   "}, {"label": "x" * 65}, {"label": 5},
        )
        for body in bad_bodies:
            self.assertEqual(self.client.post("/temperature/log/start", json=body).status_code, 400, body)
        self.assertEqual(self.client.post("/temperature/log/start", json=[1]).status_code, 400)
        self.assertIsNone(self.logger.active())

    def test_stop_without_active_log(self):
        self.assertEqual(self.client.post("/temperature/log/stop").status_code, 409)

    def test_record_log_and_summary(self):
        started = self.client.post("/temperature/log/start",
                                   json={"interval_s": 0.2, "label": "arms up / hold"})
        self.assertEqual(started.status_code, 201)
        log_id = started.json["log_id"]
        self.assertTrue(log_id.endswith("-arms-up-hold"), log_id)
        self.assertEqual(started.json["max_duration_s"], 1800.0)

        self.assertEqual(self.client.get("/temperature/log/active").json["active"]["log_id"], log_id)
        conflict = self.client.post("/temperature/log/start", json={})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json["active"]["log_id"], log_id)

        self.assertTrue(wait_until(lambda: self.logger.active()["samples"] >= 3))
        live = self.client.get("/temperature/log/%s/summary" % log_id)
        self.assertEqual(live.status_code, 200)
        self.assertTrue(live.json["active"])

        stopped = self.client.post("/temperature/log/stop")
        self.assertEqual(stopped.status_code, 200)
        summary = stopped.json
        self.assertFalse(summary["active"])
        self.assertEqual(summary["stop_reason"], "requested")
        self.assertGreaterEqual(summary["samples"], 3)
        self.assertEqual([joint["joint"] for joint in summary["joints"]], list(JOINTS))
        hottest = summary["joints"][0]
        self.assertEqual((hottest["start_c"], hottest["position_at_warning_rad"]), (30.0, -1.4))
        self.assertGreater(hottest["first_warning_s"], 0)
        self.assertEqual(hottest["mean_current_a"], 0.8)
        self.assertEqual(summary["joints"][1]["mean_current_a"], 0.4)
        self.assertIsNone(summary["joints"][1]["first_warning_s"])
        self.assertEqual(summary["joints"][2]["rise_c"], 0.0)
        self.assertIsNone(summary["joints"][3]["rise_c"])
        self.assertIsNone(self.client.get("/temperature/log/active").json["active"])

        stored = self.client.get("/temperature/log/%s/summary" % log_id)
        self.assertEqual(stored.json, summary)

        download = self.client.get("/temperature/log/%s" % log_id)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.mimetype, "text/csv")
        self.assertIn("attachment", download.headers["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(download.data.decode("utf-8"))))
        self.assertEqual(len(rows), summary["samples"] * len(JOINTS))
        self.assertEqual(list(rows[0]), temperature.CSV_FIELDS)
        hand = [row for row in rows if row["joint"] == "LHand"][0]
        self.assertEqual(hand["temperature_c"], "")

        listed = self.client.get("/temperature/log").json["logs"]
        self.assertEqual([entry["log_id"] for entry in listed], [log_id])
        self.assertEqual(listed[0]["label"], "arms up / hold")
        self.assertFalse(listed[0]["active"])

    def test_unknown_or_invalid_log_id(self):
        for log_id in ("missing", "bad.id", "a..b", "a%20b"):
            self.assertEqual(self.client.get("/temperature/log/%s" % log_id).status_code, 404, log_id)
            self.assertEqual(
                self.client.get("/temperature/log/%s/summary" % log_id).status_code, 404, log_id)

    def test_list_without_logs(self):
        temperature_api._logger = temperature.TemperatureLogger(self.log_dir + "-missing")
        self.assertEqual(self.client.get("/temperature/log").json, {"logs": []})


class TemperatureLoggerTests(OfflineCase):
    def setUp(self):
        super().setUp()
        ScriptedSensors.connect_error = None
        ScriptedSensors.fail_reads = ()
        self.log_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.log_dir, True)
        self.logger = temperature.TemperatureLogger(self.log_dir, sensors_factory=ScriptedSensors)

    def test_stops_at_max_duration(self):
        info = self.logger.start(interval_s=0.01, label="short", max_duration_s=0.1)
        self.assertTrue(wait_until(lambda: self.logger.active() is None))
        summary = self.logger.summary(info["log_id"])
        self.assertEqual(summary["stop_reason"], "max_duration")
        self.assertGreater(summary["samples"], 0)
        self.assertRaises(temperature.NotRunning, self.logger.stop)

    def test_counts_read_errors_and_keeps_logging(self):
        ScriptedSensors.fail_reads = (1, 2)
        self.logger.start(interval_s=0.01, label="flaky", max_duration_s=60)
        self.assertTrue(wait_until(lambda: self.logger.active()["samples"] >= 3))
        summary = self.logger.stop()
        self.assertEqual(summary["read_errors"], 2)
        self.assertEqual(summary["last_error"], "fake read failure")

    def test_same_second_logs_get_unique_ids(self):
        first = self.logger.start(interval_s=0.01, label="same")
        self.logger.stop()
        second = self.logger.start(interval_s=0.01, label="same")
        self.logger.stop()
        self.assertNotEqual(first["log_id"], second["log_id"])
