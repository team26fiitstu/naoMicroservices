"""Retry-aware HTTP helper for inter-service calls.

Every outbound call to another microservice goes through
`request_with_retries` so a temporarily unavailable peer is retried a
limited number of times with a delay instead of failing immediately.
After the last retry a clear error is logged and, for connection-level
failures, a `ServiceCallFailed` exception is raised. `ServiceCallFailed`
subclasses `requests.RequestException`, so existing error handling keeps
working unchanged.

Settings are read from environment variables on every call, so they can be
tuned per deployment through the root `.env` file, docker-compose or k8s:

    HTTP_RETRY_MAX_ATTEMPTS          total attempts (default 3)
    HTTP_RETRY_BACKOFF_SECONDS       initial delay between attempts (default 1.0)
    HTTP_RETRY_BACKOFF_FACTOR        multiplier applied after each attempt (default 2.0)
    HTTP_RETRY_MAX_BACKOFF_SECONDS   upper bound for a single delay (default 10.0)
    HTTP_RETRY_STATUS_CODES          comma-separated retryable HTTP statuses
                                     (default 429,500,502,503,504)
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_BACKOFF_SECONDS = 10.0
DEFAULT_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


class ServiceCallFailed(requests.RequestException):
    """Raised when an inter-service call still fails after all retries."""


class RetrySettings:
    """Resolved retry configuration for one request."""

    def __init__(self, max_attempts, backoff_seconds, backoff_factor,
                 max_backoff_seconds, retry_status_codes):
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.backoff_factor = backoff_factor
        self.max_backoff_seconds = max_backoff_seconds
        self.retry_status_codes = retry_status_codes

    def delay(self, failed_attempt):
        """Backoff delay to sleep after `failed_attempt` (1-based)."""
        raw = self.backoff_seconds * (self.backoff_factor ** (failed_attempt - 1))
        return min(max(raw, 0.0), self.max_backoff_seconds)


def _env_number(name, default):
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r, falling back to %s", name, raw, default)
        return default


def _parse_status_codes(raw):
    codes = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            codes.append(int(part))
        except ValueError:
            logger.warning("Ignoring invalid HTTP status %r in HTTP_RETRY_STATUS_CODES", part)
    return tuple(codes) or DEFAULT_RETRY_STATUS_CODES


def retry_settings(max_attempts=None, backoff_seconds=None, backoff_factor=None,
                   max_backoff_seconds=None, retry_status_codes=None):
    """Build settings from explicit values, falling back to environment variables."""
    raw_codes = os.environ.get("HTTP_RETRY_STATUS_CODES")
    if retry_status_codes is None:
        retry_status_codes = (
            _parse_status_codes(raw_codes)
            if raw_codes else DEFAULT_RETRY_STATUS_CODES
        )
    return RetrySettings(
        max_attempts=max(1, int(max_attempts if max_attempts is not None else
                                _env_number("HTTP_RETRY_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS))),
        backoff_seconds=max(0.0, backoff_seconds if backoff_seconds is not None else
                            _env_number("HTTP_RETRY_BACKOFF_SECONDS", DEFAULT_BACKOFF_SECONDS)),
        backoff_factor=max(1.0, backoff_factor if backoff_factor is not None else
                           _env_number("HTTP_RETRY_BACKOFF_FACTOR", DEFAULT_BACKOFF_FACTOR)),
        max_backoff_seconds=max(0.0, max_backoff_seconds if max_backoff_seconds is not None else
                                _env_number("HTTP_RETRY_MAX_BACKOFF_SECONDS",
                                            DEFAULT_MAX_BACKOFF_SECONDS)),
        retry_status_codes=tuple(retry_status_codes),
    )


def request_with_retries(method, url, *, sleep=time.sleep, **kwargs):
    """
    Send an HTTP request to another service, retrying limited times with a delay.

    Retries on connection errors, timeouts, and the status codes listed in
    HTTP_RETRY_STATUS_CODES (4xx client errors are never retried). Each failed
    attempt is logged as a warning; after the final attempt a clear error is
    logged and, if the last attempt raised, `ServiceCallFailed` is raised
    (subclass of `requests.RequestException`). Otherwise the final response is
    returned for the caller to inspect.

    Settings come from environment variables; they can be overridden per call
    via `max_attempts`, `backoff_seconds`, `backoff_factor`,
    `max_backoff_seconds`, and `retry_status_codes` keyword arguments.
    Remaining `**kwargs` (headers, json, params, timeout, ...) are passed to
    the underlying `requests` call.
    """
    settings = retry_settings(
        max_attempts=kwargs.pop("max_attempts", None),
        backoff_seconds=kwargs.pop("backoff_seconds", None),
        backoff_factor=kwargs.pop("backoff_factor", None),
        max_backoff_seconds=kwargs.pop("max_backoff_seconds", None),
        retry_status_codes=kwargs.pop("retry_status_codes", None),
    )
    sender = getattr(requests, method.lower())

    last_exc = None
    failure_reason = "unknown error"
    response = None

    for attempt in range(1, settings.max_attempts + 1):
        try:
            response = sender(url, **kwargs)
            if response.status_code not in settings.retry_status_codes:
                if attempt > 1:
                    logger.info("%s %s succeeded on attempt %d/%d",
                                method.upper(), url, attempt, settings.max_attempts)
                return response
            failure_reason = "HTTP %d" % response.status_code
            last_exc = None
        except requests.RequestException as exc:
            response = None
            failure_reason = "%s: %s" % (type(exc).__name__, exc)
            last_exc = exc

        if attempt < settings.max_attempts:
            delay = settings.delay(attempt)
            logger.warning("%s %s failed on attempt %d/%d (%s); retrying in %.1fs",
                           method.upper(), url, attempt, settings.max_attempts,
                           failure_reason, delay)
            sleep(delay)

    logger.error("%s %s failed after %d attempts (%s); giving up",
                 method.upper(), url, settings.max_attempts, failure_reason)
    if last_exc is not None:
        raise ServiceCallFailed(
            "%s %s failed after %d attempts: %s"
            % (method.upper(), url, settings.max_attempts, failure_reason)
        ) from last_exc
    return response