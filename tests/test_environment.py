"""Offline configuration checks; never import robot movement modules."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class EnvironmentTest(unittest.TestCase):
    def test_service_hosts_and_string_booleans(self):
        for service in ("translator", "voiceCommandAPI", "exerciseConfigService"):
            code = 'from runtime_config import compose_network, service_host; print(compose_network(), service_host("peer"))'
            for value, expected in (("false", "False localhost"), ("true", "True peer"), ("FALSE", "False localhost")):
                env = os.environ.copy()
                env["COMPOSE_NETWORK"] = value
                result = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "services" / service, env=env, text=True, capture_output=True, check=True)
                self.assertEqual(result.stdout.strip(), expected)

    def test_launcher_passes_root_file_to_local_service(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import run_local
        example = {"NAO_IP": "host.docker.internal", "NAO_PORT": "9559"}
        with patch.object(run_local, "read_env", return_value=example):
            with patch.object(sys, "argv", ["run_local.py", "translatorapi", sys.executable]):
                with patch.object(run_local.subprocess, "call", return_value=0) as call:
                    self.assertEqual(run_local.main(), 0)
        args, kwargs = call.call_args
        self.assertEqual(args[0][0], str(Path(sys.executable).resolve()))
        self.assertEqual(args[0][1], "nao_pose_service.py")
        self.assertEqual(kwargs["cwd"], str(ROOT / "services" / "translator"))
        self.assertEqual(kwargs["env"]["NAO_IP"], "127.0.0.1")
        self.assertEqual(kwargs["env"]["COMPOSE_NETWORK"], "false")

    def test_local_launcher_maps_choregraphe_and_preserves_real_address(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import run_local
        example = {"NAO_IP": "host.docker.internal", "NAO_PORT": "9559"}
        with patch.object(run_local, "read_env", return_value=example):
            self.assertEqual(run_local.environment()["NAO_IP"], "127.0.0.1")
            self.assertEqual(run_local.environment()["COMPOSE_NETWORK"], "false")
            self.assertEqual(run_local.environment()["POSE_IMAGE_DIR"], str(ROOT / "images"))
            self.assertEqual(run_local.environment()["EXERCISES_DIR"], str(ROOT / "exercises"))
        with patch.object(run_local, "read_env", return_value={"NAO_IP": "192.0.2.10", "NAO_PORT": "9559"}):
            self.assertEqual(run_local.environment()["NAO_IP"], "192.0.2.10")


if __name__ == "__main__":
    unittest.main()
