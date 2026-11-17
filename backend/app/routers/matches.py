from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.ai import features
from app.db import clean, get_db, oid
from app.security import get_current_user
from app.services import matching
from app.services.match_query import compute_matches
from app.utils import now

router = APIRouter(tags=["matching"])


async def _my_profile(user: dict) -> dict:
    me = await get_db().profiles.find_one({"user_id": user["_id"]})
    if not me:
        raise HTTPException(400, "Create your profile first")
    return me


@router.get("/matches")
async def matches(user: dict = Depends(get_current_user)):
    me = await _my_profile(user)
    blocked = {str(b) for b in user.get("blocked", [])}
    blocked_me = {str(u["_id"]) async for u in get_db().users.find({"blocked": user["_id"]}, {"_id": 1})}
    results = [m for m in await compute_matches(me, limit=30) if m["user_id"] not in blocked | blocked_me]
    sent = {str(r["to_user"]): r["status"] async for r in get_db().match_requests.find({"from_user": user["_id"]})}
    for m in results:
        m["request_status"] = sent.get(m["user_id"])
    return results


@router.get("/matches/{other_id}/summary")
async def match_summary(other_id: str, user: dict = Depends(get_current_user)):
    """AI 'why you'll get along' summary (cached)."""
    me = await _my_profile(user)
    other = await get_db().profiles.find_one({"user_id": oid(other_id)})
    if not other:
        raise HTTPException(404, "Profile not found")
    other_user = await get_db().users.find_one({"_id": other["user_id"]})
    other = {**other, "name": other_user["name"] if other_user else "They"}
    scores = matching.factor_scores(me.get("answers", {}), other.get("answers", {}))
    reasons, conflicts = matching.explain(scores, me.get("answers", {}), other.get("answers", {}))
    return await features.match_summary(me, other, reasons, conflicts, str(user["_id"]))


class RequestIn(BaseModel):
    to_user: str
    message: str = Field(default="", max_length=300)


@router.post("/requests")
async def send_request(body: RequestIn, user: dict = Depends(get_current_user)):
    to = oid(body.to_user)
    if to == user["_id"]:
        raise HTTPException(400, "You can't send a request to yourself")
    if not await get_db().users.find_one({"_id": to}):
        raise HTTPException(404, "User not found")
    try:
        res = await get_db().match_requests.insert_one(
            {"from_user": user["_id"], "to_user": to, "message": body.message, "status": "pending", "created_at": now()}
        )
    except DuplicateKeyError:
        raise HTTPException(409, "Request already sent")
    return {"id": str(res.inserted_id), "status": "pending"}


@router.get("/requests")
async def list_requests(user: dict = Depends(get_current_user)):
    db = get_db()
    reqs = [r async for r in db.match_requests.find({"$or": [{"from_user": user["_id"]}, {"to_user": user["_id"]}]}).sort("created_at", -1)]
    ids = {r["from_user"] for r in reqs} | {r["to_user"] for r in reqs}
    users = {u["_id"]: u async for u in db.users.find({"_id": {"$in": list(ids)}})}
    out = []
    for r in reqs:
        incoming = r["to_user"] == user["_id"]
        other = users.get(r["from_user"] if incoming else r["to_user"], {})
        item = {
            "id": str(r["_id"]),
            "direction": "incoming" if incoming else "outgoing",
            "status": r["status"],
            "message": r.get("message", ""),
            "other_user": {"id": str(other.get("_id")), "name": other.get("name"), "verified": other.get("verified", False)},
            "created_at": r["created_at"],
        }
        # Privacy: contact details unlock only after both sides agree.
        if r["status"] == "accepted":
            item["other_user"]["email"] = other.get("email")
        out.append(item)
    return out


@router.post("/requests/{req_id}/{action}")
async def respond(req_id: str, action: str, user: dict = Depends(get_current_user)):
    if action not in ("accept", "reject"):
        raise HTTPException(400, "Action must be accept or reject")
    r = await get_db().match_requests.find_one({"_id": oid(req_id)})
    if not r or r["to_user"] != user["_id"]:
        raise HTTPException(404, "Request not found")
    status = "accepted" if action == "accept" else "rejected"
    await get_db().match_requests.update_one({"_id": r["_id"]}, {"$set": {"status": status, "responded_at": now()}})
    return {"id": req_id, "status": status}


class ReportIn(BaseModel):
    user_id: str
    reason: str = Field(min_length=3, max_length=500)
    block: bool = True


@router.post("/reports")
async def report(body: ReportIn, user: dict = Depends(get_current_user)):
    target = oid(body.user_id)
    await get_db().reports.insert_one({"reporter": user["_id"], "reported_user": target, "reason": body.reason, "created_at": now()})
    if body.block:
        await get_db().users.update_one({"_id": user["_id"]}, {"$addToSet": {"blocked": target}})
    return {"ok": True}


@router.get("/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    if user.get("role") not in ("warden", "admin"):
        raise HTTPException(403, "Warden or admin only")
    return [clean(r) async for r in get_db().reports.find({}).sort("created_at", -1).limit(100)]
