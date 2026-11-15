"""Test configuration: expose services/common modules to the test run.

http_retry.py lives in services/common (single source of truth baked into
the service images); this makes it importable when tests run outside Docker.
"""

import os
import sys

COMMON_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "common")
)
if os.path.isdir(COMMON_DIR) and COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)