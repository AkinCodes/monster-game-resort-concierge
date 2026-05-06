"""Tests for the search_events tool — data layer + validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.events import MOCK_EVENTS, search_events  # noqa: E402
from app.core.orchestrator import ConciergeOrchestrator  # noqa: E402

_validate = ConciergeOrchestrator._validate_tool_call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_hotel_names() -> set[str]:
    return {e["hotel_name"] for e in MOCK_EVENTS}


def _all_event_types() -> set[str]:
    return {e["event_type"] for e in MOCK_EVENTS}


def _all_tags() -> set[str]:
    tags: set[str] = set()
    for e in MOCK_EVENTS:
        tags.update(e.get("tags", []))
    return tags


# ===================================================================
# 1-11  search_events data-layer tests
# ===================================================================


class TestNoFilters:
    """1. No filters — returns all events (up to default limit of 10)."""

    def test_returns_events_key(self):
        result = search_events()
        assert "events" in result

    def test_total_matches_mock_length(self):
        result = search_events()
        assert result["total"] == len(MOCK_EVENTS)

    def test_default_limit_caps_at_10(self):
        result = search_events()
        assert len(result["events"]) <= 10


class TestFilterByHotel:
    """2. Filter by hotel_name — only events from that hotel returned."""

    def test_single_hotel(self):
        hotel = "The Werewolf Lodge: Moon & Moor"
        result = search_events(hotel_name=hotel)
        assert result["total"] > 0
        for event in result["events"]:
            assert event["hotel_name"] == hotel

    def test_nonexistent_hotel_returns_empty(self):
        result = search_events(hotel_name="Nonexistent Ghost Motel")
        assert result["total"] == 0
        assert result["events"] == []


class TestFilterByEventType:
    """3. Filter by event_type — only matching event types."""

    def test_single_type(self):
        etype = "full_moon_party"
        result = search_events(event_type=etype)
        assert result["total"] > 0
        for event in result["events"]:
            assert event["event_type"] == etype

    def test_nonexistent_type_returns_empty(self):
        result = search_events(event_type="underwater_ballet")
        assert result["total"] == 0


class TestFilterByDateRange:
    """4. Filter by date range — start_after and start_before."""

    def test_start_after(self):
        result = search_events(start_after="2026-06-01")
        for event in result["events"]:
            assert event["starts_at"] > "2026-06-01"

    def test_start_before(self):
        result = search_events(start_before="2026-06-01")
        for event in result["events"]:
            assert event["starts_at"] < "2026-06-01"

    def test_date_range(self):
        result = search_events(
            start_after="2026-05-01", start_before="2026-06-01",
        )
        for event in result["events"]:
            assert "2026-05-01" < event["starts_at"] < "2026-06-01"


class TestFilterByAvailability:
    """5. Filter by has_availability=True — only available events."""

    def test_only_available(self):
        result = search_events(has_availability=True)
        for event in result["events"]:
            assert event["has_availability"] is True

    def test_unavailable_excluded(self):
        available_result = search_events(has_availability=True)
        all_result = search_events()
        unavailable_count = sum(
            1 for e in MOCK_EVENTS if not e["has_availability"]
        )
        if unavailable_count > 0:
            assert available_result["total"] < all_result["total"]


class TestFilterByTags:
    """6. Filter by tags — events matching any of the requested tags."""

    def test_single_tag(self):
        result = search_events(tags=["outdoor"])
        assert result["total"] > 0
        for event in result["events"]:
            assert "outdoor" in event["tags"]

    def test_multiple_tags_match_any(self):
        chosen = ["outdoor", "dining"]
        result = search_events(tags=chosen)
        for event in result["events"]:
            assert any(t in event["tags"] for t in chosen)

    def test_nonexistent_tag_returns_empty(self):
        result = search_events(tags=["completely_fake_tag_xyz"])
        assert result["total"] == 0


class TestSortByDateAsc:
    """7. Sort by date ascending — verify order."""

    def test_ascending_date_order(self):
        result = search_events(sort_by="date", sort_order="asc", limit=25)
        dates = [e["starts_at"] for e in result["events"]]
        assert dates == sorted(dates)


class TestSortByPriceDesc:
    """8. Sort by price descending — verify order."""

    def test_descending_price_order(self):
        result = search_events(sort_by="price", sort_order="desc", limit=25)
        prices = [e["price"] for e in result["events"]]
        assert prices == sorted(prices, reverse=True)


class TestPagination:
    """9. Pagination — limit and offset."""

    def test_limit(self):
        result = search_events(limit=3, offset=0)
        assert len(result["events"]) == 3

    def test_offset_gives_different_page(self):
        page1 = search_events(limit=3, offset=0)
        page2 = search_events(limit=3, offset=3)
        ids1 = {e["id"] for e in page1["events"]}
        ids2 = {e["id"] for e in page2["events"]}
        assert ids1.isdisjoint(ids2)

    def test_pagination_metadata(self):
        result = search_events(limit=3, offset=0)
        assert result["limit"] == 3
        assert result["offset"] == 0


class TestEmptyResults:
    """10. Empty results — filter combination that matches nothing."""

    def test_impossible_combination(self):
        result = search_events(
            hotel_name="Nonexistent Ghost Motel",
            event_type="underwater_ballet",
        )
        assert result["total"] == 0
        assert result["events"] == []


class TestCombinedFilters:
    """11. Combined filters — hotel + date range + tags together."""

    def test_hotel_date_tags(self):
        hotel = "The Werewolf Lodge: Moon & Moor"
        result = search_events(
            hotel_name=hotel,
            start_after="2026-01-01",
            start_before="2026-12-31",
            tags=["music"],
        )
        assert result["total"] > 0
        for event in result["events"]:
            assert event["hotel_name"] == hotel
            assert "2026-01-01" < event["starts_at"] < "2026-12-31"
            assert "music" in event["tags"]


# ===================================================================
# 12-15  Validation tests (_validate_tool_call for search_events)
# ===================================================================


class TestValidDateFormat:
    """12. Valid date format passes."""

    def test_valid_iso_date(self):
        ok, reason = _validate(
            "search_events",
            {"start_after": "2026-05-15"},
        )
        assert ok is True, f"Unexpected rejection: {reason}"

    def test_valid_date_range(self):
        ok, reason = _validate(
            "search_events",
            {"start_after": "2026-05-01", "start_before": "2026-05-31"},
        )
        assert ok is True


class TestInvalidDateFormat:
    """13. Invalid date format blocked."""

    def test_natural_language_date(self):
        ok, reason = _validate(
            "search_events",
            {"start_after": "next-weekend"},
        )
        assert ok is False
        assert "date" in reason.lower() or "format" in reason.lower()

    def test_wrong_format(self):
        ok, reason = _validate(
            "search_events",
            {"start_before": "05/15/2026"},
        )
        assert ok is False


class TestLimitOutOfBounds:
    """14. Limit out of bounds blocked."""

    def test_limit_too_high(self):
        ok, reason = _validate(
            "search_events",
            {"limit": 100},
        )
        assert ok is False
        assert "limit" in reason.lower()

    def test_limit_zero(self):
        ok, reason = _validate(
            "search_events",
            {"limit": 0},
        )
        assert ok is False


class TestNegativeOffset:
    """15. Negative offset blocked."""

    def test_negative_offset(self):
        ok, reason = _validate(
            "search_events",
            {"offset": -1},
        )
        assert ok is False
        assert "offset" in reason.lower()
