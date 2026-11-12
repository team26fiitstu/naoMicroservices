"""Shared helpers for hardware-free Flask route tests."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    result.raise_for_status.side_effect = (
        requests.HTTPError("upstream failed") if status >= 400 else None
    )
    return result


class OfflineCase(unittest.TestCase):
    def setUp(self):
        # Any unpatched requests call fails before a socket can be opened.
        self.network_guard = patch.object(
            requests.sessions.Session, "request",
            side_effect=AssertionError("external HTTP request attempted"),
        )
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)
