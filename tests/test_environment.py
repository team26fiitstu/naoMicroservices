"""Offline configuration checks; never import robot movement modules."""
import os
import ast
import tempfile
from unittest.mock import patch
from pathlib import Path
import subprocess
import sys
import unittest

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

    def test_entry_points_load_only_root_env_before_service_imports(self):
        entries = (
            "services/naoRobotAPI/server.py",
            "services/translator/nao_pose_service.py",
            "services/voiceCommandAPI/server.py",
            "services/exerciseConfigService/run.py",
            "services/skeletonFinderAPI/server/server.py",
            "services/audioToTextConverter/text_from_audio_extractor_service.py",
        )
        for entry in entries:
            source = (ROOT / entry).read_text()
            nodes = []
            for node in ast.parse(source).body:
                if isinstance(node, ast.Import) and any(n.name != "os" for n in node.names):
                    break
                if isinstance(node, ast.ImportFrom) and node.module != "dotenv":
                    break
                nodes.append(node)
            code = compile(ast.Module(body=nodes, type_ignores=[]), entry, "exec")
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                script = root / entry
                script.parent.mkdir(parents=True)
                (root / ".env").write_text("NAO_IP=192.0.2.10\nNAO_PORT=9561\nEXERCISES_HOST_DIR=existing\n")
                (script.parent / ".env").write_text("NAO_IP=wrong-nested-file\n")
                with patch.dict(os.environ, {}, clear=True):
                    exec(code, {"__file__": str(script)})
                    self.assertEqual(os.environ["NAO_IP"], "192.0.2.10", entry)
                    self.assertEqual(os.environ["NAO_PORT"], "9561", entry)
                    if "exerciseConfigService" in entry:
                        self.assertEqual(os.environ["EXERCISES_DIR"], str(root / "existing"))
                with patch.dict(os.environ, {"NAO_IP": "injected-host", "COMPOSE_NETWORK": "true"}, clear=True):
                    exec(code, {"__file__": str(script)})
                    self.assertEqual(os.environ["NAO_IP"], "injected-host", entry)
                if "naoRobotAPI" in entry:
                    (root / ".env").write_text("NAO_IP=host.docker.internal\nNAO_PORT=9559\n")
                    with patch.dict(os.environ, {}, clear=True):
                        exec(code, {"__file__": str(script)})
                        self.assertEqual(os.environ["NAO_IP"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
