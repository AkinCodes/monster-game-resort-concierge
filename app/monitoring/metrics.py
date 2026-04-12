from __future__ import annotations

import functools
import time

from fastapi import FastAPI, Request, Response

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    Gauge,
    generate_latest,
)
from .logging_utils import logger


# HTTP metrics
REQUEST_COUNT = Counter(
    "mrc_http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "mrc_http_request_latency_seconds", "Request latency", ["path"]
)

# Expanded metrics
ERROR_COUNT = Counter("mrc_errors_total", "Total errors", ["error_type"])
BOOKING_COUNT = Counter("mrc_bookings_total", "Total bookings", ["hotel"])
AI_TOKEN_USAGE = Counter("mrc_ai_tokens_total", "AI tokens used", ["model"])
ACTIVE_SESSIONS = Gauge("mrc_active_sessions", "Active sessions")


def track_metrics(endpoint_name):
    """Decorator to track metrics and errors for functions."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            REQUEST_COUNT.labels(
                method="function", path=endpoint_name, status="call"
            ).inc()
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                ERROR_COUNT.labels(error_type=type(e).__name__).inc()
                raise
            finally:
                elapsed = time.perf_counter() - start
                REQUEST_LATENCY.labels(endpoint_name).observe(elapsed)

        return wrapper

    return decorator


def record_booking(hotel_name):
    BOOKING_COUNT.labels(hotel=hotel_name).inc()


def record_ai_tokens(model, tokens):
    AI_TOKEN_USAGE.labels(model=model).inc(tokens)


def install_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as e:
            logger.error(f"Metrics middleware error: {e}")
            raise
        elapsed = time.perf_counter() - start
        path = request.url.path
        try:
            REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
            REQUEST_LATENCY.labels(path).observe(elapsed)
        except Exception as e:
            logger.error(f"Prometheus metrics error: {e}")
        return response

    @app.get("/metrics")
    def metrics():
        try:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
        except Exception as e:
            logger.error(f"Failed to generate metrics: {e}")
            return Response("Metrics unavailable", status_code=500)
