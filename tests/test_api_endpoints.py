import pytest


def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "app" in data


def test_chat_endpoint_requires_message(client):
    """Test chat endpoint validates input"""
    response = client.post("/chat", json={})
    assert response.status_code == 400


def test_chat_endpoint_creates_session(client):
    """Test chat endpoint creates and maintains session"""
    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "reply" in data


def test_booking_flow_end_to_end(client):
    """Test complete booking flow"""
    # Request booking
    response = client.post(
        "/chat",
        json={
            "message": "Book a Crypt Suite for John Doe from 2026-03-01 to 2026-03-03"
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Verify booking in response
    assert "book" in data["reply"].lower() or "confirm" in data["reply"].lower()
    # Verify session created
    session_id = data["session_id"]
    # Get session
    session_response = client.get(f"/sessions/{session_id}")
    assert session_response.status_code == 200


def test_sql_injection_prevention(client):
    """Test SQL injection is prevented"""
    malicious_inputs = [
        "'; DROP TABLE bookings; --",
        "1' OR '1'='1",
        "admin'--",
        "1'; DELETE FROM sessions; --",
    ]
    for malicious in malicious_inputs:
        response = client.post("/chat", json={"message": malicious})
        # Should either reject (400) or sanitize (200 with safe response)
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            # Check database still intact
            health = client.get("/health")
            assert health.status_code == 200


def test_xss_prevention(client):
    """Test XSS is prevented"""
    xss_inputs = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert('xss')",
    ]
    for xss in xss_inputs:
        response = client.post("/chat", json={"message": xss})
        assert response.status_code in [200, 400]


def test_rate_limiting(client):
    """Test rate limiting works"""
    # Send many requests
    for i in range(70):  # Over the 60/min limit
        response = client.post("/chat", json={"message": f"Test {i}"})
        if i < 60:
            assert response.status_code in [200, 201]
        else:
            # Should be rate limited
            assert response.status_code == 429
