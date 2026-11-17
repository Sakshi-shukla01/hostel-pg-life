"""MongoDB access using PyMongo's native async client.

Tests swap in an in-memory client via `set_client`.
"""
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import AsyncMongoClient

from app.config import get_settings

_client: Any = None


def set_client(client: Any) -> None:
    global _client
    _client = client


def get_db():
    global _client
    if _client is None:
        _client = AsyncMongoClient(get_settings().mongo_url)
    return _client[get_settings().mongo_db]


async def create_indexes() -> None:
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.profiles.create_index("user_id", unique=True)
    await db.profiles.create_index([("city", 1), ("gender", 1)])
    await db.match_requests.create_index([("from_user", 1), ("to_user", 1)], unique=True)
    await db.messages.create_index([("request_id", 1), ("created_at", 1)])
    await db.expenses.create_index("room_id")
    await db.complaints.create_index([("hostel", 1), ("status", 1)])
    await db.listings.create_index([("category", 1), ("status", 1)])
    await db.rule_chunks.create_index("hostel")
    await db.otps.create_index([("email", 1), ("purpose", 1)], unique=True)


def oid(value: str) -> ObjectId:
    from fastapi import HTTPException

    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def clean(doc: dict | None) -> dict | None:
    """Turn a Mongo document into JSON-friendly data (ObjectId -> str, drop secrets)."""
    if doc is None:
        return None
    out = {}
    for key, value in doc.items():
        if key == "password_hash" or key.startswith("emb_"):
            continue
        if key == "_id":
            out["id"] = str(value)
        elif isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat() + ("Z" if value.tzinfo is None else "")
        elif isinstance(value, list):
            out[key] = [str(v) if isinstance(v, ObjectId) else (clean(v) if isinstance(v, dict) else v) for v in value]
        elif isinstance(value, dict):
            out[key] = clean(value)
        else:
            out[key] = value
    return out
