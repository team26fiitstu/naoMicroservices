"""Offline configuration checks; never import robot movement modules."""
import os
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



if __name__ == "__main__":
    unittest.main()
