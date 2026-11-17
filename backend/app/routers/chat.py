"""Real-time chat between two people whose match request was accepted."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.ai import features
from app.db import clean, get_db, oid
from app.security import decode_token, get_current_user
from app.utils import now

router = APIRouter(tags=["chat"])


class Hub:
    """In-memory connections per chat. (For many servers, swap in Redis pub/sub.)"""

    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def join(self, key: str, ws: WebSocket):
        await ws.accept()
        self.rooms[key].add(ws)

    def leave(self, key: str, ws: WebSocket):
        self.rooms[key].discard(ws)

    async def send(self, key: str, data: dict):
        for ws in list(self.rooms[key]):
            try:
                await ws.send_json(data)
            except Exception:
                self.leave(key, ws)


hub = Hub()


async def _chat_for(req_id: str, user_id) -> dict:
    r = await get_db().match_requests.find_one({"_id": oid(req_id)})
    if not r or user_id not in (r["from_user"], r["to_user"]):
        raise HTTPException(404, "Chat not found")
    if r["status"] != "accepted":
        raise HTTPException(403, "Chat opens after the request is accepted")
    return r


@router.get("/chat/{req_id}/messages")
async def messages(req_id: str, user: dict = Depends(get_current_user)):
    await _chat_for(req_id, user["_id"])
    msgs = [clean(m) async for m in get_db().messages.find({"request_id": oid(req_id)}).sort("created_at", 1).limit(500)]
    return msgs


async def save_message(req_id: str, sender, text: str) -> dict:
    mod = await features.moderate(text, str(sender))
    if mod["flagged"] and "abusive" in mod["reason"]:
        return {"blocked": True, "reason": mod["reason"]}
    msg = {"request_id": oid(req_id), "sender": sender, "text": text[:2000], "created_at": now(),
           "flagged": mod["flagged"], "warning": mod["reason"]}
    res = await get_db().messages.insert_one(msg)
    msg["_id"] = res.inserted_id
    return clean(msg)


@router.websocket("/ws/chat/{req_id}")
async def chat_socket(ws: WebSocket, req_id: str, token: str):
    try:
        user_id = oid(decode_token(token))
        await _chat_for(req_id, user_id)
    except HTTPException:
        await ws.close(code=4401)
        return
    await hub.join(req_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            text = str(data.get("text", "")).strip()
            if not text:
                continue
            msg = await save_message(req_id, user_id, text)
            if msg.get("blocked"):
                await ws.send_json({"type": "error", "reason": msg["reason"]})
            else:
                await hub.send(req_id, {"type": "message", "message": msg})
    except WebSocketDisconnect:
        hub.leave(req_id, ws)
