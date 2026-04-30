"""Tests for _validate_tool_call in app/main.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import _validate_tool_call  # noqa: E402


class TestBookRoom:
    def test_valid_hotel(self):
        ok, reason = _validate_tool_call("book_room", {
            "hotel_name": "Vampire Manor: Eternal Night Inn",
        })
        assert ok is True

    def test_invalid_hotel(self):
        ok, reason = _validate_tool_call("book_room", {
            "hotel_name": "Fake Hotel",
        })
        assert ok is False
        assert "Not in official registry" in reason

    def test_empty_hotel(self):
        ok, reason = _validate_tool_call("book_room", {
            "hotel_name": "",
        })
        assert ok is False

    def test_missing_hotel_key(self):
        ok, reason = _validate_tool_call("book_room", {})
        assert ok is False


class TestGetBooking:
    def test_valid_booking_id(self):
        ok, reason = _validate_tool_call("get_booking", {
            "booking_id": "abc-123",
        })
        assert ok is True

    def test_empty_booking_id(self):
        ok, reason = _validate_tool_call("get_booking", {
            "booking_id": "",
        })
        assert ok is False
        assert "empty" in reason.lower()

    def test_whitespace_booking_id(self):
        ok, reason = _validate_tool_call("get_booking", {
            "booking_id": "   ",
        })
        assert ok is False

    def test_missing_booking_id_key(self):
        ok, reason = _validate_tool_call("get_booking", {})
        assert ok is False


class TestSearchAmenities:
    def test_valid_query(self):
        ok, reason = _validate_tool_call("search_amenities", {
            "query": "swimming pool",
        })
        assert ok is True

    def test_empty_query(self):
        ok, reason = _validate_tool_call("search_amenities", {
            "query": "",
        })
        assert ok is False
        assert "empty" in reason.lower()

    def test_whitespace_query(self):
        ok, reason = _validate_tool_call("search_amenities", {
            "query": "   ",
        })
        assert ok is False

    def test_query_too_long(self):
        ok, reason = _validate_tool_call("search_amenities", {
            "query": "x" * 501,
        })
        assert ok is False
        assert "500" in reason

    def test_query_at_limit(self):
        ok, reason = _validate_tool_call("search_amenities", {
            "query": "x" * 500,
        })
        assert ok is True


class TestUnknownTool:
    def test_unknown_tool_passes(self):
        ok, reason = _validate_tool_call("nonexistent_tool", {})
        assert ok is True

    def test_empty_args(self):
        ok, reason = _validate_tool_call("book_room", {})
        assert ok is False
