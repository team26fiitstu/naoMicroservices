#!/usr/bin/env python3
"""
voiceCommandAPI – server.py

Receives a preset voice command name from the frontend and executes
the corresponding predefined pose on the NAO robot.

Routes:
  GET  /commands          – list all supported command names and aliases
  POST /command           – execute a command  { "command": "<name>" }
  GET  /                  – health check
"""

import os
import requests
from flask import Flask, request, jsonify, send_from_directory
import flask_cors

from pose_registry import resolve, list_commands
from dotenv import load_dotenv

load_dotenv()

SERVICE_NETWORK = os.environ.get("SERVICE_NETWORK", "local").lower()
if SERVICE_NETWORK not in ("local", "docker"):
    raise ValueError("SERVICE_NETWORK must be 'local' or 'docker'")
robot_host = "naorobotapi" if SERVICE_NETWORK == "docker" else "localhost"
NAO_SET_POSE_URL = os.environ.get("NAO_SET_POSE_URL", "http://%s:5000/setting_pose/setPose" % robot_host)



IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")

app = Flask(__name__)
flask_cors.CORS(app)


# ------------------------------------------------------------------ #
# Health check                                                        #
# ------------------------------------------------------------------ #

@app.route("/", methods=["GET"])
def health():
    return "OK", 200, {"content-type": "text/plain"}


# ------------------------------------------------------------------ #
# Get a single pose (angles + description, no robot call)            #
# ------------------------------------------------------------------ #

@app.route("/pose/<pose_name>", methods=["GET"])
def get_pose(pose_name):
    """Return angles and description for a named pose without executing it."""
    try:
        name, pose = resolve(pose_name)
    except KeyError:
        available = list_commands()
        return jsonify({
            "error": f"unknown pose '{pose_name}'",
            "available_commands": available["commands"],
            "available_aliases": available["aliases"],
        }), 404

    return jsonify({
        "name": name,
        "description": pose["description"],
        "angles": pose["angles"],
    }), 200


# ------------------------------------------------------------------ #
# Serve pose image                                                    #
# ------------------------------------------------------------------ #

@app.route("/pose/<pose_name>/image", methods=["GET"])
def get_pose_image(pose_name):
    """Return the PNG image for a named pose, or 404 if not available."""
    filename = f"{pose_name}.png"
    if not os.path.isfile(os.path.join(IMAGES_DIR, filename)):
        return jsonify({"error": f"no image for pose '{pose_name}'"}), 404
    return send_from_directory(IMAGES_DIR, filename, mimetype="image/png")


# ------------------------------------------------------------------ #
# List available commands                                             #
# ------------------------------------------------------------------ #

@app.route("/commands", methods=["GET"])
def get_commands():
    """Return all supported command names and their aliases."""
    data = list_commands()
    # attach descriptions so the frontend can display them
    from pose_registry import POSES
    data["descriptions"] = {k: v["description"] for k, v in POSES.items()}
    return jsonify(data), 200


# ------------------------------------------------------------------ #
# Execute a command                                                   #
# ------------------------------------------------------------------ #

@app.route("/command", methods=["POST"])
def execute_command():
    """
    Body (JSON):
        { "command": "<command_name>" }

    Response (200):
        {
            "command": "<resolved_name>",
            "description": "...",
            "nao_response": { ... }
        }

    Errors:
        400 – missing or unknown command
        502 – NAO API unreachable
    """
    body = request.get_json(force=True, silent=True) or {}
    command_input = body.get("command", "").strip()

    if not command_input:
        return jsonify({"error": "field 'command' is required"}), 400

    try:
        pose_name, pose = resolve(command_input)
    except KeyError:
        from pose_registry import list_commands
        available = list_commands()
        return jsonify({
            "error": f"unknown command '{command_input}'",
            "available_commands": available["commands"],
            "available_aliases": available["aliases"],
        }), 400

    try:
        resp = requests.post(
            NAO_SET_POSE_URL,
            json={"angles": pose["angles"]},
            timeout=15,
        )
        resp.raise_for_status()
        nao_response = resp.json()
    except requests.RequestException as exc:
        return jsonify({
            "error": "failed to reach NAO robot API",
            "detail": str(exc),
            "command": pose_name,
        }), 502

    return jsonify({
        "command": pose_name,
        "description": pose["description"],
        "nao_response": nao_response,
    }), 200


# ------------------------------------------------------------------ #
# Entry point                                                         #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
