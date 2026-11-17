"""Sign-up verification codes, login rules, password reset and Google sign-in."""
import httpx
import pytest

from app.config import get_settings
from app.routers import auth as auth_router

pytestmark = pytest.mark.asyncio
EMAIL = "neha@gmail.com"


async def _signup(client, password="secret123"):
    return await client.post("/auth/register", json={"name": "Neha Patil", "email": EMAIL, "password": password})


async def test_signup_needs_code_before_login(client):
    assert (await _signup(client, "short")).status_code == 422  # weak password
    r = await _signup(client)
    body = r.json()
    assert body["needs_verification"] and len(body["dev_code"]) == 6 and "token" not in body
    login = await client.post("/auth/login", json={"email": EMAIL, "password": "secret123"})
    assert login.status_code == 403
    bad = await client.post("/auth/verify-email", json={"email": EMAIL, "code": "000000" if body["dev_code"] != "000000" else "111111"})
    assert bad.status_code == 400 and "4 tries left" in bad.json()["detail"]
    ok = await client.post("/auth/verify-email", json={"email": EMAIL, "code": body["dev_code"]})
    assert ok.status_code == 200 and ok.json()["user"]["email_verified"] is True
    # code is single-use
    assert (await client.post("/auth/verify-email", json={"email": EMAIL, "code": body["dev_code"]})).status_code == 400
    assert (await client.post("/auth/login", json={"email": EMAIL, "password": "secret123"})).status_code == 200
    assert (await _signup(client)).status_code == 409


async def test_resend_cooldown_and_lockout(client):
    first = (await _signup(client)).json()["dev_code"]
    assert (await client.post("/auth/resend-code", json={"email": EMAIL})).status_code == 429
    wrong = "123456" if first != "123456" else "654321"
    for _ in range(5):
        await client.post("/auth/verify-email", json={"email": EMAIL, "code": wrong})
    locked = await client.post("/auth/verify-email", json={"email": EMAIL, "code": first})
    assert locked.status_code == 429


async def test_unknown_email_gets_same_answer(client):
    r = await client.post("/auth/forgot-password", json={"email": "nobody@gmail.com"})
    assert r.status_code == 200 and r.json() == {"sent": True}


async def test_forgot_and_reset_password(client):
    code = (await _signup(client)).json()["dev_code"]
    await client.post("/auth/verify-email", json={"email": EMAIL, "code": code})
    from app import db
    await db.get_db().otps.delete_many({})  # skip the 60 s cooldown in the test
    reset = (await client.post("/auth/forgot-password", json={"email": EMAIL})).json()["dev_code"]
    weak = await client.post("/auth/reset-password", json={"email": EMAIL, "code": reset, "new_password": "abc"})
    assert weak.status_code == 422
    r = await client.post("/auth/reset-password", json={"email": EMAIL, "code": reset, "new_password": "newpass99"})
    assert r.status_code == 200 and "token" in r.json()
    assert (await client.post("/auth/login", json={"email": EMAIL, "password": "secret123"})).status_code == 401
    assert (await client.post("/auth/login", json={"email": EMAIL, "password": "newpass99"})).status_code == 200


async def test_google_sign_in(client, monkeypatch):
    assert (await client.post("/auth/google", json={"credential": "x" * 30})).status_code == 503
    monkeypatch.setattr(get_settings(), "google_client_id", "my-client.apps.googleusercontent.com")
    assert (await client.get("/auth/config")).json()["google_client_id"] == "my-client.apps.googleusercontent.com"
    claims = {"aud": "my-client.apps.googleusercontent.com", "iss": "https://accounts.google.com", "email": "riya@gmail.com",
              "email_verified": "true", "name": "Riya Gupta", "sub": "1234", "picture": "https://x/p.png"}

    async def fake_get(self, url, params=None, **kw):
        req = httpx.Request("GET", url)
        if params["id_token"] == "bad" * 10:
            return httpx.Response(400, json={"error": "invalid_token"}, request=req)
        return httpx.Response(200, json=claims, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    r = (await client.post("/auth/google", json={"credential": "good" * 10})).json()
    assert r["is_new"] and r["user"]["name"] == "Riya Gupta" and r["user"]["email_verified"]
    again = (await client.post("/auth/google", json={"credential": "good" * 10})).json()
    assert again["is_new"] is False and again["user"]["id"] == r["user"]["id"]
    assert (await client.post("/auth/google", json={"credential": "bad" * 10})).status_code == 401
    pw = await client.post("/auth/login", json={"email": "riya@gmail.com", "password": "whatever1"})
    assert pw.status_code == 400 and "Google" in pw.json()["detail"]
    claims["aud"] = "someone-else"
    assert (await client.post("/auth/google", json={"credential": "good" * 10})).status_code == 401
    h = {"Authorization": f"Bearer {r['token']}"}
    me = (await client.patch("/auth/me", json={"hostel": "Sunrise-PG"}, headers=h)).json()
    assert me["hostel"] == "sunrise-pg"
