"""Gemini path (with a faked HTTP response) and the live chat WebSocket."""
import json

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app import db
from app.ai import features, llm
from app.config import get_settings
from app.main import app


def _gemini_reply(payload) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


@pytest.mark.asyncio
async def test_gemini_json_and_onboarding(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "fake-key")
    calls = []

    async def fake_post(url, body):
        calls.append((url, body))
        return _gemini_reply({"reply": "Nice! And when do you wake up?", "profile": {"sleep_time": "01:30", "cleanliness": "7"}, "done": False})

    monkeypatch.setattr(llm, "_post", fake_post)
    out = await features.onboarding_turn([{"role": "user", "text": "I sleep at 1:30"}], {}, "u1")
    assert out["source"] == "gemini" and out["profile"] == {"sleep_time": "01:30"}  # invalid cleanliness dropped
    url, body = calls[0]
    assert url.endswith(":generateContent") and body["generationConfig"]["responseMimeType"] == "application/json"
    assert "systemInstruction" in body


@pytest.mark.asyncio
async def test_gemini_failure_falls_back(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "fake-key")

    async def broken(url, body):
        raise llm.AIUnavailable("quota exceeded")

    monkeypatch.setattr(llm, "_post", broken)
    res = await features.classify_complaint("Water leaking from tap", None, "u2")
    assert res["source"] == "offline" and res["category"] == "plumbing"
    embs = await features.embeddings_for("coding and cricket", "u2")
    assert embs["emb_gemini"] is None and len(embs["emb_local"]) == 256


def test_websocket_chat():
    db.set_client(AsyncMongoMockClient())
    with TestClient(app) as c:
        def signup(name, email):
            code = c.post("/auth/register", json={"name": name, "email": email, "password": "secret123"}).json()["dev_code"]
            return c.post("/auth/verify-email", json={"email": email, "code": code}).json()

        a, b = signup("Asha", "asha@gmail.com"), signup("Bina", "bina@gmail.com")
        ha, hb = ({"Authorization": f"Bearer {x['token']}"} for x in (a, b))
        req = c.post("/requests", json={"to_user": b["user"]["id"]}, headers=ha).json()
        c.post(f"/requests/{req['id']}/accept", headers=hb)
        with c.websocket_connect(f"/ws/chat/{req['id']}?token={a['token']}") as ws_a, \
                c.websocket_connect(f"/ws/chat/{req['id']}?token={b['token']}") as ws_b:
            ws_a.send_json({"text": "Hi Bina!"})
            assert ws_b.receive_json()["message"]["text"] == "Hi Bina!"
            assert ws_a.receive_json()["type"] == "message"
            ws_b.send_json({"text": "you idiot"})
            assert ws_b.receive_json()["type"] == "error"
        assert len(c.get(f"/chat/{req['id']}/messages", headers=ha).json()) == 1


@pytest.mark.asyncio
async def test_retry_on_503(monkeypatch):
    import httpx

    monkeypatch.setattr(get_settings(), "gemini_api_key", "fake-key")
    calls = {"n": 0}

    async def fake_send(self, request, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="overloaded", request=request)
        return httpx.Response(200, json=_gemini_reply({"ok": True}), request=request)

    async def no_sleep(_):
        return None

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)
    assert await llm.generate("hi", json_mode=True) == {"ok": True}
    assert calls["n"] == 2
