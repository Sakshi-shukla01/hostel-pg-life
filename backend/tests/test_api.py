"""End-to-end flow through the real API (in-memory MongoDB, offline AI)."""
import random

import pytest

from app import db
from app.routers.chat import save_message

pytestmark = pytest.mark.asyncio

HABITS = {"sleep_time": "01:00", "wake_time": "08:00", "cleanliness": 4, "study_style": "silent", "food": "veg",
          "smoking": False, "drinking": False, "guests": 1, "noise": 2, "ac": "fan", "personality": "introvert"}


async def register(client, name, email, role="student", hostel="sunrise-pg"):
    r = await client.post("/auth/register", json={"name": name, "email": email, "password": "secret123", "role": role, "hostel": hostel})
    assert r.status_code == 200, r.text
    code = r.json()["dev_code"]
    r = await client.post("/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return r.json()["user"]["id"], {"Authorization": f"Bearer {r.json()['token']}"}


async def make_profile(client, h, **over):
    body = {"city": "Pune", "area": "Kothrud", "gender": "female", "budget_min": 6000, "budget_max": 9000,
            "move_in": "2026-12-01", "bio": "Final year CSE student, love coding and cricket, quiet person.",
            "interests": ["coding", "cricket"], "answers": HABITS}
    body.update(over)
    r = await client.put("/profile", json=body, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_full_flow(client):
    priya, hp = await register(client, "Priya Sharma", "priya@coep.ac.in")
    ananya, ha = await register(client, "Ananya Rao", "ananya@gmail.com")
    _, hr = await register(client, "Rahul", "rahul@gmail.com")
    _, hw = await register(client, "Warden Mehta", "warden@sunrise.in", role="warden")

    me = (await client.get("/auth/me", headers=hp)).json()
    assert me["verified"] is True and "password_hash" not in me

    await make_profile(client, hp)
    await make_profile(client, ha, bio="I like programming and football, calm and quiet.", answers={**HABITS, "sleep_time": "00:30", "ac": "ac"})
    await make_profile(client, hr, gender="male")  # filtered out by gender preference

    # --- AI onboarding chat (offline mode)
    t = (await client.post("/ai/onboarding", json={"history": [], "profile": {}}, headers=hp)).json()
    assert "sleep" in t["reply"].lower()
    t = (await client.post("/ai/onboarding", json={"history": [{"role": "assistant", "text": t["reply"]}, {"role": "user", "text": "around 1am"}], "profile": {}}, headers=hp)).json()
    assert t["profile"]["sleep_time"] == "01:00" and "wake" in t["reply"].lower()

    # --- Matching
    matches = (await client.get("/matches", headers=hp)).json()
    assert [m["name"] for m in matches] == ["Ananya Rao"]
    m = matches[0]
    assert m["score"] > 70 and m["reasons"] and any("AC" in c for c in m["conflicts"])
    summary = (await client.get(f"/matches/{ananya}/summary", headers=hp)).json()
    assert "Ananya" in summary["text"]

    # --- Requests, contact unlock, chat
    req = (await client.post("/requests", json={"to_user": ananya, "message": "Hi!"}, headers=hp)).json()
    assert (await client.post("/requests", json={"to_user": ananya}, headers=hp)).status_code == 409
    incoming = (await client.get("/requests", headers=ha)).json()
    assert incoming[0]["direction"] == "incoming" and "email" not in incoming[0]["other_user"]
    assert (await client.get(f"/chat/{req['id']}/messages", headers=hp)).status_code == 403
    await client.post(f"/requests/{req['id']}/accept", headers=ha)
    accepted = (await client.get("/requests", headers=hp)).json()[0]
    assert accepted["other_user"]["email"] == "ananya@gmail.com"

    from bson import ObjectId
    ok = await save_message(req["id"], ObjectId(priya), "Hey, when are you moving in?")
    assert ok["text"].startswith("Hey")
    scam = await save_message(req["id"], ObjectId(ananya), "Please share OTP for deposit")
    assert scam["flagged"]
    abusive = await save_message(req["id"], ObjectId(ananya), "you idiot")
    assert abusive.get("blocked")
    msgs = (await client.get(f"/chat/{req['id']}/messages", headers=ha)).json()
    assert len(msgs) == 2

    # --- Room, expenses, balances, chores, agreement, ratings
    room = (await client.post("/rooms", json={"name": "Room 204", "request_id": req["id"]}, headers=hp)).json()
    assert len(room["members"]) == 2
    await client.post("/rooms/me/expenses", json={"title": "Rent", "amount": 16000, "category": "rent"}, headers=hp)
    await client.post("/rooms/me/expenses", json={"title": "Wi-Fi", "amount": 800, "category": "wifi"}, headers=ha)
    r = (await client.get("/rooms/me", headers=hp)).json()
    assert r["balances"][priya] == 7600 and r["payments"] == [{"from_user": ananya, "to_user": priya, "amount": 7600.0}]
    await client.post("/rooms/me/settle", json={"to_user": priya, "amount": 7600}, headers=ha)
    assert (await client.get("/rooms/me", headers=hp)).json()["payments"] == []
    bad = await client.post("/rooms/me/expenses", json={"title": "x", "amount": 100, "split": "custom", "shares": {priya: 30, ananya: 30}}, headers=hp)
    assert bad.status_code == 400

    chore = (await client.post("/rooms/me/chores", json={"task": "Clean bathroom"}, headers=hp)).json()
    first = chore["assigned_to"]
    rotated = (await client.post(f"/rooms/me/chores/{chore['id']}/done", headers=hp)).json()
    assert rotated["assigned_to"] != first and rotated["done_count"] == 1
    agreement = (await client.post("/rooms/me/agreement/generate", headers=hp)).json()
    assert "Quiet hours" in agreement["text"]
    await client.post("/rooms/me/agreement/accept", headers=ha)
    assert (await client.post("/rooms/me/rate", json={"to_user": ananya, "stars": 5}, headers=hp)).status_code == 200
    assert (await client.post("/rooms/me/scan-bill", files={"photo": ("b.png", b"\x89PNG....", "image/png")}, headers=hp)).status_code == 503

    # --- Complaints
    c = (await client.post("/complaints", data={"title": "Fan not working", "description": "Ceiling fan stopped, sparks from switch", "room_no": "204"}, headers=hp)).json()
    assert c["category"] == "electrical" and c["priority"] == "high" and c["status"] == "open"
    assert (await client.get("/complaints", headers=hp)).status_code == 403
    listing = (await client.get("/complaints", headers=hw)).json()
    assert listing[0]["id"] == c["id"]
    await client.patch(f"/complaints/{c['id']}", json={"status": "resolved", "note": "Electrician fixed it"}, headers=hw)
    assert (await client.post(f"/complaints/{c['id']}/rate", json={"stars": 4}, headers=hp)).status_code == 200
    stats = (await client.get("/complaints/stats", headers=hw)).json()
    assert stats["total"] == 1 and stats["avg_rating"] == 4

    # --- Marketplace
    fill = (await client.post("/market/autofill", data={"hint": "air cooler"}, headers=hp)).json()
    assert fill["category"] == "appliances" and fill["suggested_price"] > 0
    item = (await client.post("/market", data={"title": "Symphony air cooler", "price": 1800, "category": "appliances"}, headers=hp)).json()
    assert item["status"] == "available"
    scam_item = (await client.post("/market", data={"title": "iPhone cheap", "description": "pay first via UPI then I ship", "price": 5000, "category": "electronics"}, headers=ha)).json()
    assert scam_item["status"] == "under_review"
    found = (await client.get("/market", params={"q": "cooler", "max_price": 2000}, headers=ha)).json()
    assert [x["title"] for x in found] == ["Symphony air cooler"]
    contact = (await client.post(f"/market/{item['id']}/interested", headers=ha)).json()
    assert contact["seller_email"] == "priya@coep.ac.in"

    # --- Rules bot (RAG)
    rules = ("1. The main gate closes at 10:30 PM on weekdays and 11:30 PM on weekends.\n\n"
             "2. Visitors are allowed in the common room only, between 5 PM and 8 PM.\n\n"
             "3. Cooking appliances like induction stoves are not allowed in rooms.\n\n"
             "4. Rent must be paid by the 5th of every month; late fee is Rs 100 per day.")
    up = (await client.post("/rules/upload", data={"text": rules}, headers=hw)).json()
    assert up["chunks"] >= 1
    ans = (await client.post("/rules/ask", json={"question": "What time does the gate close?"}, headers=hp)).json()
    assert "10:30" in ans["answer"]

    # --- AI assistant (agent, offline intent mode)
    a = (await client.post("/assistant", json={"question": "Find me a veg non-smoker roommate"}, headers=hp)).json()
    assert "Ananya" in a["answer"] and a["steps"][0]["tool"] == "search_roommates"
    a = (await client.post("/assistant", json={"question": "who owes money in my room?"}, headers=hp)).json()
    assert a["answer"] == "All settled up!"
    a = (await client.post("/assistant", json={"question": "any cooler under 2000?"}, headers=ha)).json()
    assert "cooler" in a["answer"].lower()
    a = (await client.post("/assistant", json={"question": "what are the visitor rules?"}, headers=hp)).json()
    assert "Visitors" in a["answer"] or "visitor" in a["answer"].lower()

    # --- Report + block hides the match
    await client.post("/reports", json={"user_id": ananya, "reason": "Rude in chat"}, headers=hp)
    assert (await client.get("/matches", headers=hp)).json() == []


async def test_learning_matcher(client):
    _, hw = await register(client, "Warden", "w@x.in", role="warden")
    database = db.get_db()
    rnd = random.Random(1)
    ids = []
    for i in range(30):
        _, h = await register(client, f"User {i}", f"u{i}@gmail.com")
        ans = {**HABITS, "sleep_time": rnd.choice(["22:00", "23:00", "00:00", "01:00", "02:00"]), "cleanliness": rnd.randint(1, 5)}
        p = await make_profile(client, h, answers=ans)
        ids.append(p["user_id"])
    from bson import ObjectId
    from app.services import matching

    profiles = {p["user_id"]: p async for p in database.profiles.find({})}
    for i in range(0, 30, 2):
        for j in (i + 1, (i + 3) % 30):
            a, b = profiles[ObjectId(ids[i])], profiles[ObjectId(ids[j])]
            s = matching.factor_scores(a["answers"], b["answers"])
            happy = s["sleep_time"] >= 0.5  # ground truth: sleep decides happiness
            await database.ratings.insert_one({"from_user": a["user_id"], "to_user": b["user_id"], "stars": 5 if happy else 2})

    result = (await client.post("/ml/train", headers=hw)).json()
    assert result["trained"] is True and result["n_ratings"] == 30
    assert result["weights"]["sleep_time"] == max(result["weights"].values())
    status = (await client.get("/ml/status", headers=hw)).json()
    assert status["ratings"] == 30
