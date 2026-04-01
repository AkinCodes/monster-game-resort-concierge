def test_rag_policy_answer(client):
    r = client.post("/chat", json={"session_id":"s2", "message":"What time is check in?"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "Check-in" in data["reply"] or "check-in" in data["reply"].lower()
