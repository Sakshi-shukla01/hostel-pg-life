"""Second-hand marketplace for students, with AI autofill and scam checks."""
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.ai import features
from app.db import clean, get_db, oid
from app.security import get_current_user
from app.utils import now, save_image

router = APIRouter(prefix="/market", tags=["marketplace"])
CATS = features.LISTING_CATS


@router.post("/autofill")
async def autofill(hint: str = Form("", max_length=80), photo: UploadFile | None = File(None), user: dict = Depends(get_current_user)):
    """Photo (and/or a hint like 'cooler') -> title, category, condition, description, suggested price."""
    if not hint and photo is None:
        raise HTTPException(400, "Add a photo or a short hint")
    _, image = await save_image(photo) if photo else (None, None)
    return await features.autofill_listing(hint or "item", image, str(user["_id"]))


@router.post("")
async def create_listing(
    title: str = Form(..., min_length=2, max_length=80),
    description: str = Form("", max_length=600),
    price: float = Form(..., ge=0, le=500000),
    category: str = Form("other"),
    condition: str = Form("good"),
    location: str = Form("", max_length=80),
    photo: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    if category not in CATS:
        raise HTTPException(400, f"Category must be one of {CATS}")
    url, _ = await save_image(photo)
    mod = await features.moderate(f"{title}. {description}", str(user["_id"]), use_llm=True)
    doc = {
        "seller": user["_id"], "seller_name": user["name"], "seller_verified": user.get("verified", False),
        "title": title, "description": description, "price": price, "category": category, "condition": condition,
        "location": location or user.get("hostel", ""), "photo_url": url,
        "status": "under_review" if mod["flagged"] else "available", "flag_reason": mod["reason"], "created_at": now(),
    }
    res = await get_db().listings.insert_one(doc)
    doc["_id"] = res.inserted_id
    return clean(doc)


@router.get("")
async def search(q: str = "", category: str = "", max_price: float | None = None, user: dict = Depends(get_current_user)):
    query: dict = {"status": "available"}
    if q:
        query["$or"] = [{"title": {"$regex": re.escape(q), "$options": "i"}}, {"description": {"$regex": re.escape(q), "$options": "i"}}]
    if category:
        query["category"] = category
    if max_price is not None:
        query["price"] = {"$lte": max_price}
    return [clean(x) async for x in get_db().listings.find(query).sort("created_at", -1).limit(60)]


@router.get("/mine")
async def mine(user: dict = Depends(get_current_user)):
    return [clean(x) async for x in get_db().listings.find({"seller": user["_id"]}).sort("created_at", -1)]


@router.post("/{lid}/sold")
async def mark_sold(lid: str, user: dict = Depends(get_current_user)):
    res = await get_db().listings.update_one({"_id": oid(lid), "seller": user["_id"]}, {"$set": {"status": "sold"}})
    if not res.matched_count:
        raise HTTPException(404, "Listing not found")
    return {"ok": True}


@router.post("/{lid}/interested")
async def interested(lid: str, user: dict = Depends(get_current_user)):
    """Share the buyer's interest with the seller (contact via email to keep it simple)."""
    item = await get_db().listings.find_one({"_id": oid(lid)})
    if not item:
        raise HTTPException(404, "Listing not found")
    await get_db().listings.update_one({"_id": item["_id"]}, {"$addToSet": {"interested": {"user": user["_id"], "name": user["name"], "email": user["email"]}}})
    seller = await get_db().users.find_one({"_id": item["seller"]})
    return {"seller_name": seller["name"] if seller else "", "seller_email": seller["email"] if seller else ""}
