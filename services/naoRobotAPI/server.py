
import os
from dotenv import load_dotenv

# Load only the repository root file; container environment takes precedence.
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))
if os.environ.get("COMPOSE_NETWORK", "false").lower() != "true" and os.environ.get("NAO_IP") == "host.docker.internal":
    os.environ["NAO_IP"] = "127.0.0.1"

import sys
import threading
import time
from collections import deque
from flask import Flask, g, request, jsonify
import flask_cors

try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)

from robot_module_testing.test_api import test_api
from robot.setting_pose.setting_pose_api import setting_pose_api
from robot.voice_lines.voice_lines_api import voice_lines_api
from robot.temperature.temperature_api import temperature_api

app = Flask(
    __name__,
    static_url_path="",
    static_folder="web/static",
    template_folder="web/templates",
)

flask_cors.CORS(app)
app.register_blueprint(test_api, url_prefix="/tests")
app.register_blueprint(setting_pose_api, url_prefix="/setting_pose")
app.register_blueprint(voice_lines_api, url_prefix="/voiceLines")
app.register_blueprint(temperature_api, url_prefix="/temperature")

# All robot-changing routes share one lock, including commands from translator,
# voiceCommandAPI, and the direct robot API. Keep it through the NAOqi call.
_robot_command_lock = threading.Lock()
_reservation_lock = threading.Lock()
_robot_command_blueprints = frozenset(("test_api", "setting_pose_api", "voice_lines_api"))
_reservation = {"token": None, "expires_at": 0}
RESERVATION_SECONDS = 120
RETIRED_TOKEN_LIMIT = 1000
_retired_tokens = set()
_retired_token_order = deque()


def _reserved_token():
    if _reservation["token"] and time.time() >= _reservation["expires_at"]:
        _reservation["token"] = None
        _reservation["expires_at"] = 0
    return _reservation["token"]


def _retire_token(token):
    if token not in _retired_tokens:
        _retired_tokens.add(token)
        _retired_token_order.append(token)
        if len(_retired_token_order) > RETIRED_TOKEN_LIMIT:
            _retired_tokens.remove(_retired_token_order.popleft())


@app.before_request
def serialize_robot_commands():
    if request.blueprint in _robot_command_blueprints:
        _robot_command_lock.acquire()
        g.robot_command_lock_held = True
        with _reservation_lock:
            token = _reserved_token()
        if token and request.headers.get("X-Robot-Run-Token") != token:
            return jsonify({"error": "robot is reserved by a choreography run"}), 409


@app.teardown_request
def release_robot_command_lock(error):
    if getattr(g, "robot_command_lock_held", False):
        _robot_command_lock.release()


@app.route("/control/reservation", methods=["POST", "DELETE"])
def robot_reservation():
    data = request.get_json(silent=True)
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, string_types) or not token:
        return jsonify({"error": "token is required"}), 400
    if request.method == "POST":
        # Renewal must work while a long robot call holds the command lock.
        with _reservation_lock:
            if token in _retired_tokens:
                return jsonify({"error": "reservation was already released"}), 409
            if _reserved_token() == token:
                _reservation["expires_at"] = time.time() + RESERVATION_SECONDS
                return jsonify({"success": True}), 200
        if not _robot_command_lock.acquire(False):
            return jsonify({"error": "robot command is in progress"}), 409
        try:
            with _reservation_lock:
                if token in _retired_tokens:
                    return jsonify({"error": "reservation was already released"}), 409
                owner = _reserved_token()
                if owner and owner != token:
                    return jsonify({"error": "robot is reserved by another run"}), 409
                _reservation["token"] = token
                _reservation["expires_at"] = time.time() + RESERVATION_SECONDS
        finally:
            _robot_command_lock.release()
    else:
        with _robot_command_lock:
            with _reservation_lock:
                owner = _reserved_token()
                _retire_token(token)
                if owner is not None and owner != token:
                    return jsonify({"error": "reservation is not owned by this run"}), 409
                if owner == token:
                    _reservation["token"] = None
                    _reservation["expires_at"] = 0
    return jsonify({"success": True}), 200


@app.route("/", methods=["GET"])
def check_if_service_is_up():
    return "OK", 200, {"content-type": "text/html"}


with app.app_context():
    print("Preparing for requests execution...")
    # g.fully_automated_product_lines_knowledge_manager = FullyAutomatedProductLinesKnowledgeManager()
    print("Preparation completed successfully!")


def launch():
    app.run(host="0.0.0.0", debug=False, port=5000)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "production":
        app.run(host="0.0.0.0", debug=False, port=5000)
    else:
        app.run(host="0.0.0.0", debug=True, port=5000)
