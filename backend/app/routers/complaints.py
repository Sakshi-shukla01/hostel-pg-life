"""Hostel/PG complaints with AI categorising and 48-hour escalation."""
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.ai import features
from app.db import clean, get_db, oid
from app.security import get_current_user, require_warden
from app.utils import now, save_image

router = APIRouter(prefix="/complaints", tags=["complaints"])
ESCALATE_AFTER = timedelta(hours=48)
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _view(c: dict) -> dict:
    out = clean(c)
    out["escalated"] = c["status"] != "resolved" and now() - c["created_at"] > ESCALATE_AFTER
    return out


@router.post("")
async def raise_complaint(
    title: str = Form(..., min_length=3, max_length=100),
    description: str = Form("", max_length=1000),
    room_no: str = Form("", max_length=20),
    photo: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    url, image = await save_image(photo)
    ai = await features.classify_complaint(f"{title}. {description}", image, str(user["_id"]))
    doc = {
        "raised_by": user["_id"], "raiser_name": user["name"], "hostel": user.get("hostel", "default"),
        "title": title, "description": description, "room_no": room_no, "photo_url": url,
        "category": ai["category"], "priority": ai["priority"], "ai_summary": ai["summary"], "ai_source": ai["source"],
        "status": "open", "notes": [], "rating": None, "created_at": now(), "resolved_at": None,
    }
    res = await get_db().complaints.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _view(doc)


@router.get("/mine")
async def mine(user: dict = Depends(get_current_user)):
    return [_view(c) async for c in get_db().complaints.find({"raised_by": user["_id"]}).sort("created_at", -1)]


@router.get("")
async def all_for_hostel(status: str | None = None, warden: dict = Depends(require_warden)):
    q: dict = {"hostel": warden.get("hostel", "default")}
    if status:
        q["status"] = status
    items = [_view(c) async for c in get_db().complaints.find(q)]
    # Escalated first, then by priority, then oldest first
    items.sort(key=lambda c: (not c["escalated"], PRIORITY_ORDER.get(c["priority"], 3), c["created_at"]))
    return items


class UpdateIn(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
    note: str = Field(default="", max_length=300)


@router.patch("/{cid}")
async def update(cid: str, body: UpdateIn, warden: dict = Depends(require_warden)):
    c = await get_db().complaints.find_one({"_id": oid(cid), "hostel": warden.get("hostel", "default")})
    if not c:
        raise HTTPException(404, "Complaint not found")
    change: dict = {"$set": {"status": body.status, "resolved_at": now() if body.status == "resolved" else None}}
    if body.note:
        change["$push"] = {"notes": {"by": warden["name"], "text": body.note, "at": now()}}
    await get_db().complaints.update_one({"_id": c["_id"]}, change)
    return _view(await get_db().complaints.find_one({"_id": c["_id"]}))


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)


@router.post("/{cid}/rate")
async def rate(cid: str, body: RateIn, user: dict = Depends(get_current_user)):
    res = await get_db().complaints.update_one({"_id": oid(cid), "raised_by": user["_id"], "status": "resolved"}, {"$set": {"rating": body.stars}})
    if not res.matched_count:
        raise HTTPException(400, "You can rate only your own resolved complaints")
    return {"ok": True}


@router.get("/stats")
async def stats(warden: dict = Depends(require_warden)):
    items = [c async for c in get_db().complaints.find({"hostel": warden.get("hostel", "default")})]
    by_cat: dict[str, int] = {}
    for c in items:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    resolved = [c for c in items if c.get("resolved_at")]
    avg_hours = round(sum((c["resolved_at"] - c["created_at"]).total_seconds() for c in resolved) / 3600 / len(resolved), 1) if resolved else None
    ratings = [c["rating"] for c in items if c.get("rating")]
    return {
        "total": len(items),
        "open": sum(c["status"] != "resolved" for c in items),
        "escalated": sum(c["status"] != "resolved" and now() - c["created_at"] > ESCALATE_AFTER for c in items),
        "by_category": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
        "avg_resolution_hours": avg_hours,
        "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
    }
