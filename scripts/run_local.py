#!/usr/bin/env python3
"""Load the single root .env and run one service without Docker."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {
    "naorobotapi": ("naoRobotAPI", "server.py"),
    "skeletonfinderapi": ("skeletonFinderAPI/server", "server.py"),
    "translatorapi": ("translator", "nao_pose_service.py"),
    "voicecommandapi": ("voiceCommandAPI", "server.py"),
    "exercise-config-service": ("exerciseConfigService", "run.py"),
    "audio-to-text-converter": ("audioToTextConverter", "text_from_audio_extractor_service.py"),
}


def read_env(path):
    if not path.is_file():
        raise FileNotFoundError("Copy .env.example to the repository root .env first")
    values = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Invalid .env line %d" % number)
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def environment():
    env = os.environ.copy()
    env.update(read_env(ROOT / ".env"))
    env["COMPOSE_NETWORK"] = "false"
    if env.get("NAO_IP") == "host.docker.internal":
        env["NAO_IP"] = "127.0.0.1"
    env["POSE_IMAGE_DIR"] = str(ROOT / "images")
    env["POSE_SERVICE_IMAGE_DIR"] = env["POSE_IMAGE_DIR"]
    env["EXERCISES_DIR"] = str((ROOT / env.get("EXERCISES_HOST_DIR", "exercises")).resolve())
    return env


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in SERVICES:
        print("Usage: python3 scripts/run_local.py SERVICE PYTHON_EXECUTABLE", file=sys.stderr)
        print("Services: " + ", ".join(SERVICES), file=sys.stderr)
        return 2
    service_dir, script = SERVICES[sys.argv[1]]
    env = environment()
    (ROOT / "images").mkdir(exist_ok=True)
    Path(env["EXERCISES_DIR"]).mkdir(parents=True, exist_ok=True)
    executable = str(Path(sys.argv[2]).resolve()) if "/" in sys.argv[2] or "\\" in sys.argv[2] else sys.argv[2]
    return subprocess.call([executable, script], cwd=str(ROOT / "services" / service_dir), env=env)


if __name__ == "__main__":
    sys.exit(main())
