"""Shared process environment conventions for Python 3 services."""
import os


def compose_network():
    value = os.environ.get("COMPOSE_NETWORK", "false").strip().lower()
    if value not in ("true", "false"):
        raise ValueError("COMPOSE_NETWORK must be true or false")
    return value == "true"


def service_host(name):
    return name if compose_network() else "localhost"
