"""
Unit tests for http_retry.py.

Verifies that inter-service calls retry a limited number of times with a
delay, that 4xx responses are never retried, that a clear error is raised
and logged after the last retry, and that settings are configurable via
environment variables.
"""

import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import http_retry
from http_retry import ServiceCallFailed, request_with_retries, retry_settings


def make_response(status_code=200, payload=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = payload if payload is not None else {}
    return resp


def no_sleep(_seconds):
    pass


# ---------------------------------------------------------------------------
# Successful calls: no retries
# ---------------------------------------------------------------------------

def test_success_first_attempt_calls_once():
    with patch("http_retry.requests.get", return_value=make_response(200)) as mock_get:
        resp = request_with_retries("GET", "http://svc/endpoint", sleep=no_sleep)

    assert resp.status_code == 200
    assert mock_get.call_count == 1


def test_forwards_kwargs_to_requests():
    with patch("http_retry.requests.post", return_value=make_response(201)) as mock_post:
        request_with_retries(
            "POST", "http://svc/create", json={"a": 1}, timeout=5, sleep=no_sleep
        )

    mock_post.assert_called_once_with("http://svc/create", json={"a": 1}, timeout=5)


# ---------------------------------------------------------------------------
# Retries with delay on transient failures
# ---------------------------------------------------------------------------

def test_retries_connection_error_then_succeeds():
    responses = [requests.ConnectionError("refused"), make_response(200)]

    with patch("http_retry.requests.get", side_effect=responses) as mock_get:
        resp = request_with_retries("GET", "http://svc/endpoint", sleep=no_sleep)

    assert resp.status_code == 200
    assert mock_get.call_count == 2


def test_retries_retryable_status_then_succeeds():
    responses = [make_response(503), make_response(200)]

    with patch("http_retry.requests.get", side_effect=responses) as mock_get:
        resp = request_with_retries("GET", "http://svc/endpoint", sleep=no_sleep)

    assert resp.status_code == 200
    assert mock_get.call_count == 2


def test_delay_grows_with_backoff_factor():
    delays = []
    responses = [requests.ConnectionError("x"), requests.ConnectionError("x"),
                 make_response(200)]

    with patch("http_retry.requests.get", side_effect=responses):
        request_with_retries(
            "GET", "http://svc/endpoint", max_attempts=3,
            backoff_seconds=1.0, backoff_factor=2.0, sleep=delays.append,
        )

    assert delays == [1.0, 2.0]


def test_delay_is_capped_by_max_backoff():
    delays = []
    responses = [requests.ConnectionError("x"), requests.ConnectionError("x"),
                 make_response(200)]

    with patch("http_retry.requests.get", side_effect=responses):
        request_with_retries(
            "GET", "http://svc/endpoint", max_attempts=3,
            backoff_seconds=1.0, backoff_factor=10.0,
            max_backoff_seconds=2.0, sleep=delays.append,
        )

    assert delays == [1.0, 2.0]  # 1.0*10^0 uncapped; 1.0*10^1 capped at 2.0


# ---------------------------------------------------------------------------
# 4xx responses are never retried
# ---------------------------------------------------------------------------

def test_client_error_not_retried():
    with patch("http_retry.requests.get", return_value=make_response(404)) as mock_get:
        resp = request_with_retries("GET", "http://svc/endpoint", sleep=no_sleep)

    assert resp.status_code == 404
    assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# Clear error after the last retry
# ---------------------------------------------------------------------------

def test_raises_clear_error_after_last_attempt(caplog):
    with patch("http_retry.requests.get",
               side_effect=requests.ConnectionError("connection refused")) as mock_get:
        with caplog.at_level(logging.ERROR, logger="http_retry"):
            with pytest.raises(ServiceCallFailed) as excinfo:
                request_with_retries(
                    "GET", "http://svc/endpoint",
                    max_attempts=3, backoff_seconds=0.0, sleep=no_sleep,
                )

    assert mock_get.call_count == 3
    message = str(excinfo.value)
    assert "GET http://svc/endpoint" in message
    assert "3 attempts" in message
    assert "connection refused" in message
    # ServiceCallFailed keeps requests.RequestException compatibility
    assert isinstance(excinfo.value, requests.RequestException)
    # the final failure was logged clearly
    assert any("failed after 3 attempts" in rec.message for rec in caplog.records)


def test_last_5xx_response_is_logged_and_returned(caplog):
    resp5xx = make_response(503)

    with patch("http_retry.requests.get", side_effect=[make_response(503), resp5xx]):
        with caplog.at_level(logging.ERROR, logger="http_retry"):
            result = request_with_retries(
                "GET", "http://svc/endpoint",
                max_attempts=2, backoff_seconds=0.0, sleep=no_sleep,
            )

    assert result is resp5xx
    assert any("failed after 2 attempts" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Configurable settings
# ---------------------------------------------------------------------------

def test_defaults_without_env(monkeypatch):
    monkeypatch.delenv("HTTP_RETRY_MAX_ATTEMPTS", raising=False)
    settings = retry_settings()
    assert settings.max_attempts == 3
    assert settings.backoff_seconds == 1.0
    assert settings.backoff_factor == 2.0
    assert settings.max_backoff_seconds == 10.0
    assert settings.retry_status_codes == (429, 500, 502, 503, 504)


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("HTTP_RETRY_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("HTTP_RETRY_BACKOFF_SECONDS", "0.5")
    monkeypatch.setenv("HTTP_RETRY_BACKOFF_FACTOR", "3")
    monkeypatch.setenv("HTTP_RETRY_MAX_BACKOFF_SECONDS", "4")
    monkeypatch.setenv("HTTP_RETRY_STATUS_CODES", "500, 503")

    settings = retry_settings()
    assert settings.max_attempts == 5
    assert settings.backoff_seconds == 0.5
    assert settings.backoff_factor == 3.0
    assert settings.max_backoff_seconds == 4.0
    assert settings.retry_status_codes == (500, 503)

    responses = [make_response(503), make_response(503), make_response(503),
                 make_response(200)]
    with patch("http_retry.requests.get", side_effect=responses) as mock_get:
        resp = request_with_retries("GET", "http://svc/endpoint", sleep=no_sleep)

    assert resp.status_code == 200
    assert mock_get.call_count == 4


def test_invalid_env_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("HTTP_RETRY_MAX_ATTEMPTS", "not-a-number")
    assert retry_settings().max_attempts == 3


def test_explicit_override_beats_env(monkeypatch):
    monkeypatch.setenv("HTTP_RETRY_MAX_ATTEMPTS", "5")
    with patch("http_retry.requests.get",
               side_effect=requests.ConnectionError("x")) as mock_get:
        with pytest.raises(ServiceCallFailed):
            request_with_retries(
                "GET", "http://svc/endpoint",
                max_attempts=2, backoff_seconds=0.0, sleep=no_sleep,
            )
    assert mock_get.call_count == 2


def test_shared_module_source_of_truth():
    """http_retry.py must live in services/common, not be duplicated per service."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    module_dir = os.path.dirname(os.path.abspath(http_retry.__file__))
    # the module we imported resolves to a shared "common" directory
    assert os.path.basename(module_dir) == "common"
    # inside the repository that directory is services/common
    if os.path.isdir(os.path.join(root, "services", "common")):
        assert module_dir == os.path.join(root, "services", "common")
    # no per-service copies remain
    for service in ("translator", "voiceCommandAPI", "exerciseConfigService"):
        stale = os.path.join(root, "services", service, "http_retry.py")
        assert not os.path.exists(stale), f"remove duplicated copy: {stale}"