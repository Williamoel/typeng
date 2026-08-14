"""Lightweight request timing for local and hosted TypEng deployments."""

from __future__ import annotations

import logging
import time

from flask import Flask, g, request


LOGGER = logging.getLogger("typeng.performance")


def register_request_timing(app: Flask, slow_request_ms: float = 500.0) -> None:
    """Expose request duration and log unexpectedly slow endpoints.

    ``Server-Timing`` is visible in browser developer tools and can also be
    asserted by benchmarks without adding a metrics service to the local app.
    """

    @app.before_request
    def _start_request_timer() -> None:
        g.typeng_request_started_at = time.perf_counter()

    @app.after_request
    def _finish_request_timer(response):
        started_at = getattr(g, "typeng_request_started_at", None)
        if started_at is None:
            return response
        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
        if duration_ms >= slow_request_ms:
            LOGGER.warning(
                "slow request method=%s path=%s status=%s duration_ms=%.1f",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
            )
        return response

