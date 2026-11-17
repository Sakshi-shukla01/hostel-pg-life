from app.db import get_db
from app.services import splitting


async def room_for(user_id) -> dict | None:
    return await get_db().rooms.find_one({"members": user_id})


async def room_summary(room: dict) -> dict:
    db = get_db()
    expenses = [e async for e in db.expenses.find({"room_id": room["_id"]})]
    settlements = [s async for s in db.settlements.find({"room_id": room["_id"]})]
    plain = [{"paid_by": str(e["paid_by"]), "amount": e["amount"], "shares": e["shares"]} for e in expenses]
    plain_s = [{"from_user": str(s["from_user"]), "to_user": str(s["to_user"]), "amount": s["amount"]} for s in settlements]
    bal = splitting.balances(plain, plain_s)
    for m in room["members"]:
        bal.setdefault(str(m), 0.0)
    return {"balances": bal, "payments": splitting.simplify(bal), "expenses": expenses, "settlements": settlements}
