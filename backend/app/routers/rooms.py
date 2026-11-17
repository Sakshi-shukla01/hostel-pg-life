"""Room groups: expenses, bill scanning, settle-up, chores, agreement, ratings."""
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.ai import features
from app.ai.llm import AIUnavailable
from app.db import clean, get_db, oid
from app.security import get_current_user
from app.services import splitting
from app.services.room_query import room_for, room_summary
from app.utils import now, save_image

router = APIRouter(prefix="/rooms", tags=["rooms"])


async def _my_room(user: dict) -> dict:
    room = await room_for(user["_id"])
    if not room:
        raise HTTPException(404, "You are not in a room yet")
    return room


class RoomIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    request_id: str


@router.post("")
async def create_room(body: RoomIn, user: dict = Depends(get_current_user)):
    db = get_db()
    r = await db.match_requests.find_one({"_id": oid(body.request_id)})
    if not r or r["status"] != "accepted" or user["_id"] not in (r["from_user"], r["to_user"]):
        raise HTTPException(400, "You need an accepted match request to create a room")
    members = [r["from_user"], r["to_user"]]
    existing = await db.rooms.find_one({"members": {"$in": members}})
    if existing:
        # Third roommate joins the existing room (3-sharing).
        await db.rooms.update_one({"_id": existing["_id"]}, {"$addToSet": {"members": {"$each": members}}})
        return clean(await db.rooms.find_one({"_id": existing["_id"]}))
    room = {"name": body.name, "members": members, "agreement": None, "created_at": now()}
    res = await db.rooms.insert_one(room)
    room["_id"] = res.inserted_id
    return clean(room)


@router.get("/me")
async def my_room(user: dict = Depends(get_current_user)):
    db = get_db()
    room = await room_for(user["_id"])
    if not room:
        return None
    summary = await room_summary(room)
    members = [u async for u in db.users.find({"_id": {"$in": room["members"]}})]
    chores = [clean(c) async for c in db.chores.find({"room_id": room["_id"]})]
    return {
        **clean(room),
        "members": [{"id": str(m["_id"]), "name": m["name"], "email": m["email"]} for m in members],
        "balances": summary["balances"],
        "payments": summary["payments"],
        "expenses": [clean(e) for e in sorted(summary["expenses"], key=lambda e: e["created_at"], reverse=True)],
        "chores": chores,
        "rated": [str(x["to_user"]) async for x in db.ratings.find({"room_id": room["_id"], "from_user": user["_id"]})],
    }


class ExpenseIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0, le=1_000_000)
    category: Literal["rent", "electricity", "wifi", "groceries", "maid", "water", "gas", "food", "other"] = "other"
    paid_by: str | None = None
    split: Literal["equal", "custom"] = "equal"
    shares: dict[str, float] | None = None


@router.post("/me/expenses")
async def add_expense(body: ExpenseIn, user: dict = Depends(get_current_user)):
    room = await _my_room(user)
    members = [str(m) for m in room["members"]]
    payer = body.paid_by or str(user["_id"])
    if payer not in members:
        raise HTTPException(400, "Payer must be in the room")
    try:
        if body.split == "custom":
            if not body.shares or any(k not in members for k in body.shares):
                raise ValueError("Custom shares must use room member ids")
            shares = splitting.shares_for(body.amount, members, body.shares)
        else:
            shares = splitting.shares_for(body.amount, members)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    doc = {"room_id": room["_id"], "title": body.title, "amount": round(body.amount, 2), "category": body.category,
           "paid_by": oid(payer), "shares": shares, "added_by": user["_id"], "created_at": now()}
    res = await get_db().expenses.insert_one(doc)
    doc["_id"] = res.inserted_id
    return clean(doc)


@router.delete("/me/expenses/{expense_id}")
async def delete_expense(expense_id: str, user: dict = Depends(get_current_user)):
    room = await _my_room(user)
    res = await get_db().expenses.delete_one({"_id": oid(expense_id), "room_id": room["_id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Expense not found")
    return {"ok": True}


@router.post("/me/scan-bill")
async def scan_bill(photo: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Photo of a bill -> {title, amount, category}. The user confirms before saving."""
    await _my_room(user)
    _, image = await save_image(photo)
    try:
        return await features.scan_bill(image, str(user["_id"]))
    except AIUnavailable as exc:
        raise HTTPException(503, str(exc))


class SettleIn(BaseModel):
    to_user: str
    amount: float = Field(gt=0)


@router.post("/me/settle")
async def settle(body: SettleIn, user: dict = Depends(get_current_user)):
    room = await _my_room(user)
    if oid(body.to_user) not in room["members"]:
        raise HTTPException(400, "That person is not in your room")
    await get_db().settlements.insert_one({"room_id": room["_id"], "from_user": user["_id"], "to_user": oid(body.to_user),
                                           "amount": round(body.amount, 2), "created_at": now()})
    return {"ok": True}


class ChoreIn(BaseModel):
    task: str = Field(min_length=2, max_length=60)
    every_days: int = Field(default=7, ge=1, le=31)


@router.post("/me/chores")
async def add_chore(body: ChoreIn, user: dict = Depends(get_current_user)):
    room = await _my_room(user)
    count = await get_db().chores.count_documents({"room_id": room["_id"]})
    assignee = room["members"][count % len(room["members"])]  # spread chores across members
    doc = {"room_id": room["_id"], "task": body.task, "every_days": body.every_days, "assigned_to": assignee,
           "done_count": 0, "last_done": None, "created_at": now()}
    res = await get_db().chores.insert_one(doc)
    doc["_id"] = res.inserted_id
    return clean(doc)


@router.post("/me/chores/{chore_id}/done")
async def chore_done(chore_id: str, user: dict = Depends(get_current_user)):
    """Mark done and rotate to the next roommate."""
    room = await _my_room(user)
    chore = await get_db().chores.find_one({"_id": oid(chore_id), "room_id": room["_id"]})
    if not chore:
        raise HTTPException(404, "Chore not found")
    members = room["members"]
    idx = members.index(chore["assigned_to"]) if chore["assigned_to"] in members else 0
    nxt = members[(idx + 1) % len(members)]
    await get_db().chores.update_one({"_id": chore["_id"]}, {"$set": {"assigned_to": nxt, "last_done": now()}, "$inc": {"done_count": 1}})
    return clean(await get_db().chores.find_one({"_id": chore["_id"]}))


@router.post("/me/agreement/generate")
async def generate_agreement(user: dict = Depends(get_current_user)):
    room = await _my_room(user)
    db = get_db()
    profiles = []
    for m in room["members"]:
        p = await db.profiles.find_one({"user_id": m}) or {}
        u = await db.users.find_one({"_id": m}) or {}
        profiles.append({"name": u.get("name"), "answers": p.get("answers", {})})
    result = await features.roommate_agreement(profiles, str(user["_id"]))
    agreement = {"text": result["text"], "source": result["source"], "agreed_by": [], "created_at": now()}
    await db.rooms.update_one({"_id": room["_id"]}, {"$set": {"agreement": agreement}})
    return clean(agreement)


@router.post("/me/agreement/accept")
async def accept_agreement(user: dict = Depends(get_current_user)):
    room = await _my_room(user)
    if not room.get("agreement"):
        raise HTTPException(400, "Generate an agreement first")
    await get_db().rooms.update_one({"_id": room["_id"]}, {"$addToSet": {"agreement.agreed_by": user["_id"]}})
    return {"ok": True}


class RatingIn(BaseModel):
    to_user: str
    stars: int = Field(ge=1, le=5)


@router.post("/me/rate")
async def rate_roommate(body: RatingIn, user: dict = Depends(get_current_user)):
    """After living together, rate the match. These ratings train the learning matcher."""
    room = await _my_room(user)
    to = oid(body.to_user)
    if to not in room["members"] or to == user["_id"]:
        raise HTTPException(400, "Rate a roommate from your room")
    await get_db().ratings.update_one(
        {"room_id": room["_id"], "from_user": user["_id"], "to_user": to},
        {"$set": {"stars": body.stars, "created_at": now()}}, upsert=True,
    )
    return {"ok": True}
