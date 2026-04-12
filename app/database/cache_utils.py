import functools
import hashlib
import threading
from collections import OrderedDict
from time import monotonic
from typing import Callable

CACHE_TTL_SECONDS = 300  # 5 minutes
CACHE_MAX_SIZE = 256


class TTLCache:
    """Thread-safe, size-bounded cache with per-entry TTL expiry."""

    def __init__(self, maxsize: int = CACHE_MAX_SIZE, ttl: int = CACHE_TTL_SECONDS):
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            if key not in self._cache:
                return None
            value, expires = self._cache[key]
            if monotonic() >= expires:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, monotonic() + self._ttl)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


def _make_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Build a stable, hashable cache key from function name + arguments."""
    parts = [func_name]
    for arg in args:
        parts.append(
            f"{type(arg).__name__}:{id(arg) if hasattr(arg, '__dict__') else repr(arg)}"  # noqa: E231
        )
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={repr(v)}")
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def cache_response(ttl: int = CACHE_TTL_SECONDS):
    """Decorator that caches function results with TTL expiry and LRU eviction."""
    _ttl_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=ttl)

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = _make_key(func.__name__, args, kwargs)
            cached = _ttl_cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            _ttl_cache.set(key, result)
            return result

        wrapper.cache = _ttl_cache
        return wrapper

    return decorator


# Problem: Unbounded memory
#   Fix: CACHE_MAX_SIZE = 256 — oldest entry evicted when full (LRU via
#     OrderedDict)
#   ────────────────────────────────────────
#   Problem: Expired entries linger
#   Fix: Expired entries are deleted on access, not just skipped
#   ────────────────────────────────────────
#   Problem: self in cache key
#   Fix: _make_key uses id(obj) for objects (same instance = same key), repr() for

#     primitives
#   ────────────────────────────────────────
#   Problem: Unhashable kwargs crash
#   Fix: Key is built with repr() + hashed to MD5 — works with any argument type
#   ────────────────────────────────────────
#   Problem: Not thread-safe
#   Fix: threading.Lock() around all reads/writes
#   ────────────────────────────────────────
#   Problem: No external dependencies
#   Fix: Zero new packages — stdlib only (OrderedDict, threading, hashlib)
#   The @cache_response(ttl=300) decorator API is identical, so vector_rag.py and
#   advanced_rag.py need no changes.
