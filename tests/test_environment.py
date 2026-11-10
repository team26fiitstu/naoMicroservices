"""Offline configuration checks; never import robot movement modules."""
import os
import ast
import json
import re
import shutil
import types
import tempfile
from unittest.mock import patch
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EnvironmentTest(unittest.TestCase):
    def test_standalone_movement_script_uses_root_env_without_sdk_calls(self):
        entry = "services/naoRobotAPI/robot_module_testing/movement_test.py"
        source = (ROOT / entry).read_text()
        sdk = types.ModuleType("naoqi")

        def unexpected_robot_call(*args, **kwargs):
            self.fail("The offline import must not connect to NAO")

        sdk.ALProxy = unexpected_robot_call
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / entry
            script.parent.mkdir(parents=True)
            (root / ".env").write_text("NAO_IP=192.0.2.10\nNAO_PORT=9561\n")
            scope = {"__file__": str(script), "__name__": "offline_review"}
            with patch.dict(os.environ, {}, clear=True), patch.dict(sys.modules, {"naoqi": sdk}):
                exec(compile(source, str(script), "exec"), scope)
                self.assertEqual(scope["NAO_IP"], "192.0.2.10")
                self.assertEqual(scope["NAO_PORT"], 9561)
                self.assertEqual(
                    scope["NAOController"].__init__.__defaults__,
                    ("192.0.2.10", 9561),
                )

    def test_service_hosts_and_string_booleans(self):
        for service in ("translator", "voiceCommandAPI", "exerciseConfigService"):
            code = 'from runtime_config import compose_network, service_host; print(compose_network(), service_host("peer"))'
            for value, expected in (("false", "False localhost"), ("true", "True peer"), ("FALSE", "False localhost")):
                env = os.environ.copy()
                env["COMPOSE_NETWORK"] = value
                result = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "services" / service, env=env, text=True, capture_output=True, check=True)
                self.assertEqual(result.stdout.strip(), expected)

    @unittest.skipUnless(shutil.which("docker"), "Docker CLI is required")
    def test_web_dependencies_cover_static_nginx_upstreams(self):
        config = json.loads(subprocess.check_output(
            ["docker", "compose", "-f", "docker-compose.dev.yml", "config", "--format", "json"],
            cwd=ROOT, text=True,
        ))
        services = config["services"]
        dependencies = set()

        def visit(name):
            if name in dependencies:
                return
            dependencies.add(name)
            for dependency in services[name].get("depends_on", {}):
                visit(dependency)

        visit("web")
        nginx = (ROOT / "web/nginx-conf/default.conf").read_text()
        nginx = "\n".join(line.split("#", 1)[0] for line in nginx.splitlines())
        upstreams = set(re.findall(r"proxy_pass\s+http://([^:/;]+)", nginx))
        self.assertTrue(upstreams)
        self.assertFalse(upstreams - dependencies, upstreams - dependencies)

    def test_entry_points_load_only_root_env_before_service_imports(self):
        entries = (
            "services/naoRobotAPI/server.py",
            "services/naoRobotAPI/robot_module_testing/movement_test.py",
            "services/naoRobotAPI/robot_module_testing/test.py",
            "services/naoRobotAPI/robot_module_testing/body_balancer_test.py",
            "services/naoRobotAPI/robot_module_testing/dt.py",
            "services/naoRobotAPI/robot_module_testing/face_follow.py",
            "services/naoRobotAPI/robot/dalsie_skusanie_poz.py",
            "services/translator/nao_pose_service.py",
            "services/voiceCommandAPI/server.py",
            "services/exerciseConfigService/run.py",
            "services/skeletonFinderAPI/server/server.py",
            "services/audioToTextConverter/text_from_audio_extractor_service.py",
        )
        for entry in entries:
            source = (ROOT / entry).read_text()
            # Stop before SDK/service imports, including Python 2-only bodies.
            lines = source.splitlines()
            for number, line in enumerate(lines):
                if line.startswith(("import ", "from ")):
                    module = line.split()[1]
                    if module not in ("os", "dotenv"):
                        source = "\n".join(lines[:number])
                        break
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
