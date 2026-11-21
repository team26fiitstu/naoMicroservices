# -*- coding: utf-8 -*-
"""HTTP routes for reading and logging NAO joint temperatures (read-only)."""
import json
import numbers
import os

from flask import Blueprint, Response, request

from .temperature import AlreadyRunning, NotRunning, TemperatureLogger, snapshot

MIN_INTERVAL_S = 0.2
MAX_INTERVAL_S = 60.0
DEFAULT_MAX_DURATION_S = 1800.0
MAX_DURATION_LIMIT_S = 4 * 3600.0
MAX_LABEL_LENGTH = 64

SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_LOG_DIR = os.path.abspath(os.path.join(SERVICE_DIR, "..", "..", "logs", "temperature"))

temperature_api = Blueprint("temperature_api", __name__)
_logger = None


def get_logger():
    global _logger
    if _logger is None:
        _logger = TemperatureLogger(os.environ.get("TEMPERATURE_LOG_DIR", DEFAULT_LOG_DIR))
    return _logger


def application_json_response(payload, status):
    return json.dumps(payload), status, {"content-type": "application/json"}


def _robot_unavailable(error):
    return application_json_response({"error": "NAO robot is unavailable", "detail": str(error)}, 503)


def _positive_number(data, key, default, minimum, maximum):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a number" % key)
    value = float(value)
    if not minimum <= value <= maximum:
        raise ValueError("%s must be between %g and %g" % (key, minimum, maximum))
    return value


@temperature_api.route("", methods=["GET"])
def read_snapshot():
    try:
        return application_json_response(snapshot(get_logger().sensors_factory), 200)
    except Exception as error:
        return _robot_unavailable(error)


@temperature_api.route("/log/start", methods=["POST"])
def start_log():
    data = request.get_json(force=True, silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return application_json_response({"error": "request body must be a JSON object"}, 400)
    try:
        interval_s = _positive_number(data, "interval_s", 1.0, MIN_INTERVAL_S, MAX_INTERVAL_S)
        max_duration_s = _positive_number(
            data, "max_duration_s", DEFAULT_MAX_DURATION_S, 1.0, MAX_DURATION_LIMIT_S)
    except ValueError as error:
        return application_json_response({"error": str(error)}, 400)
    label = data.get("label", "exercise")
    if not isinstance(label, type(u"")) and not isinstance(label, str):
        return application_json_response({"error": "label must be a string"}, 400)
    if not label.strip() or len(label) > MAX_LABEL_LENGTH:
        return application_json_response(
            {"error": "label must be 1 to %d characters" % MAX_LABEL_LENGTH}, 400)
    try:
        info = get_logger().start(interval_s=interval_s, label=label.strip(), max_duration_s=max_duration_s)
    except AlreadyRunning as error:
        return application_json_response({"error": str(error), "active": error.active}, 409)
    except Exception as error:
        return _robot_unavailable(error)
    return application_json_response(info, 201)


@temperature_api.route("/log/stop", methods=["POST"])
def stop_log():
    try:
        return application_json_response(get_logger().stop(), 200)
    except NotRunning as error:
        return application_json_response({"error": str(error)}, 409)


@temperature_api.route("/log/active", methods=["GET"])
def active_log():
    return application_json_response({"active": get_logger().active()}, 200)


@temperature_api.route("/log", methods=["GET"])
def list_logs():
    return application_json_response({"logs": get_logger().list_logs()}, 200)


@temperature_api.route("/log/<log_id>", methods=["GET"])
def download_log(log_id):
    try:
        path = get_logger().csv_path(log_id)
    except KeyError:
        return application_json_response({"error": "log '%s' not found" % log_id}, 404)
    with open(path, "rb") as handle:
        content = handle.read()
    return Response(content, mimetype="text/csv", headers={
        "Content-Disposition": "attachment; filename=%s.csv" % log_id,
    })


@temperature_api.route("/log/<log_id>/summary", methods=["GET"])
def log_summary(log_id):
    try:
        return application_json_response(get_logger().summary(log_id), 200)
    except KeyError:
        return application_json_response({"error": "summary for log '%s' not found" % log_id}, 404)
