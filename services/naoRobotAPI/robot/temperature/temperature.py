# -*- coding: utf-8 -*-
"""Read-only joint sensor sampling and temperature logging for NAO.

This module only reads ALMemory values; it never sends motion or stiffness
commands. It runs on Python 2.7 in the NAOqi container and on Python 3 in the
offline test suite, so it avoids syntax and APIs that exist in only one of them.
"""
from __future__ import division, print_function

import csv
import json
import numbers
import os
import re
import sys
import threading
import time

from naoqi import ALProxy

# Output field name -> ALMemory sub-key of Device/SubDeviceList/<Joint>/.
SENSORS = (
    ("temperature_c", "Temperature/Sensor/Value"),
    ("status", "Temperature/Sensor/Status"),
    ("position_rad", "Position/Sensor/Value"),
    ("current_a", "ElectricCurrent/Sensor/Value"),
)
CSV_FIELDS = ["timestamp", "elapsed_s", "joint"] + [name for name, _ in SENSORS]
LOG_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class AlreadyRunning(Exception):
    def __init__(self, active):
        Exception.__init__(self, "a temperature log is already running")
        self.active = active


class NotRunning(Exception):
    pass


def nao_address():
    return os.environ.get("NAO_IP", "127.0.0.1"), int(os.environ.get("NAO_PORT", 9559))


def iso_timestamp(epoch_seconds):
    millis = int((epoch_seconds - int(epoch_seconds)) * 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch_seconds)) + ".%03dZ" % millis


def _number(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    value = float(value)
    return None if value != value else value  # NaN -> None


class NaoSensors(object):
    """Reads temperature, temperature status, position and current of every joint."""

    def __init__(self, proxy_factory=None):
        proxy_factory = proxy_factory or ALProxy
        ip, port = nao_address()
        self.memory = proxy_factory("ALMemory", ip, port)
        motion = proxy_factory("ALMotion", ip, port)
        self.joints = [str(joint) for joint in motion.getBodyNames("Body")]
        self.keys = [
            "Device/SubDeviceList/%s/%s" % (joint, sub_key)
            for joint in self.joints
            for _, sub_key in SENSORS
        ]

    def _read_values(self):
        try:
            values = self.memory.getListData(self.keys)
            if values is not None and len(values) == len(self.keys):
                return list(values)
        except Exception:
            pass
        # getListData returns None for missing keys (e.g. Choregraphe's virtual robot
        # only has Temperature/Sensor/Status); fall back to per-key reads only if the
        # batch call itself fails.
        values = []
        for key in self.keys:
            try:
                values.append(self.memory.getData(key))
            except Exception:
                values.append(None)
        return values

    def read(self):
        """Return {joint: {field: float or None}}."""
        values = iter(self._read_values())
        result = {}
        for joint in self.joints:
            result[joint] = dict((name, _number(next(values))) for name, _ in SENSORS)
        return result


def snapshot(sensors_factory=NaoSensors, clock=time.time):
    sensors = sensors_factory()
    return {"timestamp": iso_timestamp(clock()), "joints": sensors.read()}


def _open_csv_for_writing(path):
    if sys.version_info[0] < 3:
        return open(path, "wb")
    return open(path, "w", newline="")


def _makedirs(path):
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise


def _slug(label):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-")
    return slug[:40] or "log"


class _JointStats(object):
    def __init__(self):
        self.start_c = None
        self.max_c = None
        self.first_warning_s = None
        self.position_at_warning_rad = None
        self.current_sum = 0.0
        self.current_count = 0

    def add(self, elapsed_s, values):
        temperature = values.get("temperature_c")
        if temperature is not None:
            if self.start_c is None:
                self.start_c = temperature
            if self.max_c is None or temperature > self.max_c:
                self.max_c = temperature
        status = values.get("status")
        if self.first_warning_s is None and status is not None and status > 0:
            self.first_warning_s = elapsed_s
            self.position_at_warning_rad = values.get("position_rad")
        current = values.get("current_a")
        if current is not None:
            self.current_sum += abs(current)
            self.current_count += 1

    def as_dict(self, joint):
        rise = None
        if self.start_c is not None and self.max_c is not None:
            rise = round(self.max_c - self.start_c, 2)
        mean_current = None
        if self.current_count:
            mean_current = round(self.current_sum / self.current_count, 4)
        return {
            "joint": joint,
            "start_c": self.start_c,
            "max_c": self.max_c,
            "rise_c": rise,
            "first_warning_s": self.first_warning_s,
            "position_at_warning_rad": self.position_at_warning_rad,
            "mean_current_a": mean_current,
        }


def _heating_order(entry):
    # Joints that NAO flagged as hot come first (earliest warning first),
    # then the largest temperature rise; joints without data go last.
    warned = entry["first_warning_s"] is not None
    rise = entry["rise_c"]
    return (
        0 if warned else 1,
        entry["first_warning_s"] if warned else 0,
        0 if rise is not None else 1,
        -(rise or 0),
        entry["joint"],
    )


class _Recording(object):
    def __init__(self, log_id, label, interval_s, max_duration_s, csv_path, summary_path, clock):
        self.log_id = log_id
        self.label = label
        self.interval_s = interval_s
        self.max_duration_s = max_duration_s
        self.csv_path = csv_path
        self.summary_path = summary_path
        self.clock = clock
        self.started = clock()
        self.stopped = None
        self.stop_reason = None
        self.samples = 0
        self.read_errors = 0
        self.last_error = None
        self.stats = {}
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = threading.Lock()

    def info(self):
        return {
            "log_id": self.log_id,
            "label": self.label,
            "started_at": iso_timestamp(self.started),
            "interval_s": self.interval_s,
            "max_duration_s": self.max_duration_s,
            "samples": self.samples,
        }

    def summary(self):
        with self.lock:
            end = self.stopped if self.stopped is not None else self.clock()
            joints = [stats.as_dict(joint) for joint, stats in self.stats.items()]
            joints.sort(key=_heating_order)
            return {
                "log_id": self.log_id,
                "label": self.label,
                "active": self.stopped is None,
                "started_at": iso_timestamp(self.started),
                "stopped_at": iso_timestamp(self.stopped) if self.stopped is not None else None,
                "stop_reason": self.stop_reason,
                "interval_s": self.interval_s,
                "max_duration_s": self.max_duration_s,
                "duration_s": round(end - self.started, 3),
                "samples": self.samples,
                "read_errors": self.read_errors,
                "last_error": self.last_error,
                "joints": joints,
            }


class TemperatureLogger(object):
    """Records one temperature log at a time in a background thread."""

    def __init__(self, log_dir, sensors_factory=NaoSensors, clock=time.time):
        self.log_dir = log_dir
        self.sensors_factory = sensors_factory
        self.clock = clock
        self._lock = threading.Lock()
        self._active = None

    # ---------------------------------------------------------------- paths
    def _path(self, log_id, suffix):
        if not LOG_ID_PATTERN.match(log_id or ""):
            raise KeyError(log_id)
        return os.path.join(self.log_dir, log_id + suffix)

    def csv_path(self, log_id):
        path = self._path(log_id, ".csv")
        if not os.path.isfile(path):
            raise KeyError(log_id)
        return path

    # ------------------------------------------------------------ lifecycle
    def start(self, interval_s=1.0, label="exercise", max_duration_s=1800):
        with self._lock:
            if self._active is not None:
                raise AlreadyRunning(self._active.info())
            # Fail fast with a clear error if NAOqi is unreachable.
            self.sensors_factory().read()
            _makedirs(self.log_dir)
            started = self.clock()
            base_id = time.strftime("%Y%m%d-%H%M%S", time.gmtime(started)) + "-" + _slug(label)
            log_id = base_id
            counter = 2
            while os.path.exists(os.path.join(self.log_dir, log_id + ".csv")):
                log_id = "%s-%d" % (base_id, counter)
                counter += 1
            recording = _Recording(
                log_id, label, interval_s, max_duration_s,
                os.path.join(self.log_dir, log_id + ".csv"),
                os.path.join(self.log_dir, log_id + ".summary.json"),
                self.clock,
            )
            with _open_csv_for_writing(recording.csv_path) as handle:
                csv.writer(handle).writerow(CSV_FIELDS)
            recording.thread = threading.Thread(target=self._run, args=(recording,))
            recording.thread.daemon = True
            self._active = recording
            recording.thread.start()
            return recording.info()

    def stop(self):
        with self._lock:
            recording = self._active
        if recording is None:
            raise NotRunning("no temperature log is running")
        recording.stop_event.set()
        recording.thread.join()
        return recording.summary()

    def active(self):
        with self._lock:
            recording = self._active
        return recording.info() if recording is not None else None

    def summary(self, log_id):
        with self._lock:
            recording = self._active
        if recording is not None and recording.log_id == log_id:
            return recording.summary()
        path = self._path(log_id, ".summary.json")
        if not os.path.isfile(path):
            raise KeyError(log_id)
        with open(path) as handle:
            return json.load(handle)

    def list_logs(self):
        if not os.path.isdir(self.log_dir):
            return []
        active = self.active()
        logs = []
        for name in sorted(os.listdir(self.log_dir), reverse=True):
            if not name.endswith(".csv"):
                continue
            log_id = name[:-len(".csv")]
            entry = {"log_id": log_id, "active": bool(active and active["log_id"] == log_id)}
            summary_path = os.path.join(self.log_dir, log_id + ".summary.json")
            if os.path.isfile(summary_path):
                try:
                    with open(summary_path) as handle:
                        data = json.load(handle)
                    for key in ("label", "started_at", "duration_s", "samples", "stop_reason"):
                        entry[key] = data.get(key)
                except ValueError:
                    pass
            logs.append(entry)
        return logs

    # --------------------------------------------------------------- worker
    def _run(self, recording):
        stop_reason = "requested"
        try:
            sensors = self.sensors_factory()
            next_sample = recording.started
            while not recording.stop_event.is_set():
                now = self.clock()
                elapsed = now - recording.started
                if elapsed >= recording.max_duration_s:
                    stop_reason = "max_duration"
                    break
                try:
                    values = sensors.read()
                except Exception as error:
                    with recording.lock:
                        recording.read_errors += 1
                        recording.last_error = str(error)
                else:
                    self._write_sample(recording, now, elapsed, values)
                next_sample += recording.interval_s
                recording.stop_event.wait(max(0.0, next_sample - self.clock()))
        except Exception as error:
            stop_reason = "error"
            with recording.lock:
                recording.last_error = str(error)
        finally:
            self._finish(recording, stop_reason)

    def _write_sample(self, recording, now, elapsed, values):
        timestamp = iso_timestamp(now)
        elapsed = round(elapsed, 3)
        rows = []
        for joint in sorted(values):
            joint_values = values[joint]
            rows.append([timestamp, elapsed, joint] + [
                "" if joint_values.get(name) is None else joint_values.get(name)
                for name, _ in SENSORS
            ])
        mode = "ab" if sys.version_info[0] < 3 else "a"
        kwargs = {} if sys.version_info[0] < 3 else {"newline": ""}
        with open(recording.csv_path, mode, **kwargs) as handle:
            csv.writer(handle).writerows(rows)
        with recording.lock:
            recording.samples += 1
            for joint, joint_values in values.items():
                recording.stats.setdefault(joint, _JointStats()).add(elapsed, joint_values)

    def _finish(self, recording, stop_reason):
        with recording.lock:
            recording.stopped = self.clock()
            recording.stop_reason = stop_reason
        summary = recording.summary()
        try:
            with open(recording.summary_path, "w") as handle:
                json.dump(summary, handle, indent=2)
        finally:
            with self._lock:
                if self._active is recording:
                    self._active = None
