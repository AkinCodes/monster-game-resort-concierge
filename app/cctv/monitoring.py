from __future__ import annotations

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


import functools
import time


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


# 1. The Hotel Guests (HTTP Requests)
# Every time someone calls your API, it’s like a guest visiting your hotel:
# REQUEST_COUNT → counts how many guests have arrived, and records things like
# which room they went to (endpoint path), what method they used, and if they checked in successfully (status).
# REQUEST_LATENCY → measures how long it takes to serve each guest (how long the request took).
# 2. Mistakes or Problems (Errors)
# Sometimes guests cause problems:
# ERROR_COUNT → keeps track of all errors that happen, grouped by type of
# problem (like a guest spilling coffee vs. losing a key).
# 3. Special Activities
# Some guests do specific things:
# BOOKING_COUNT → counts how many rooms are booked, grouped by hotel (like counting how many bookings each hotel has).
# AI_TOKEN_USAGE → counts how many AI “tokens” were used, like tracking how many resources a guest used at the hotel spa.
# ACTIVE_SESSIONS → keeps a live count of guests currently in the hotel.
# 4. Metrics Tracking Helper (track_metrics)
# Think of track_metrics as a hotel staff member who watches a guest’s activity:
# They start a stopwatch when a guest arrives.
# They note if anything goes wrong (increment error counters).
# When the guest leaves, they record how long the visit took.
# This happens automatically for any decorated function (endpoint).
# 5. Middleware (metrics_middleware)
# This is like a hotel receptionist at the front desk:
# Every time a guest walks in, they note arrival time.
# After the guest is done and leaves, they record the total time and increment counters.
# If something goes wrong at the desk, they log the problem.
# 6. Metrics Endpoint (/metrics)
# This is like a dashboard in the hotel office:
# Anyone (like Prometheus) can look at the dashboard to see how many guests, errors, bookings, or AI tokens were used.
# If the dashboard breaks, the receptionist writes “Metrics unavailable”.
