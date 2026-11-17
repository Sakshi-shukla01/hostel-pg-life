"""AI roommate assistant: an agent that answers questions by calling the app's own tools.

With Gemini: the model picks a tool (JSON), we run it, feed back the result,
and repeat (max 4 steps) until it gives a final answer.
Offline: keyword intent detection picks the tool, and a template writes the answer.
Every tool is read-only, so the agent can never change data by mistake.
"""
import json
import re

from app.ai import llm
from app.ai.features import _can_use_ai
from app.ai.llm import AIUnavailable
from app.db import get_db
from app.services import rag
from app.services.match_query import compute_matches
from app.services.room_query import room_for, room_summary

TOOLS = {
    "search_roommates": "Find compatible roommates. args: food (veg|nonveg|eggetarian|flexible), smoking (true|false), max_budget (number, rupees/month), area (text). All optional.",
    "my_balances": "Who owes whom in the user's room. No args.",
    "my_complaints": "The user's complaints and their status. No args.",
    "search_listings": "Search the second-hand marketplace. args: query (text), max_price (number), category (books|electronics|appliances|furniture|cycles|other). All optional.",
    "hostel_rules": "Answer a question from the hostel/PG rulebook. args: question (text).",
}


async def _names(ids) -> dict[str, str]:
    from bson import ObjectId

    oids = [ObjectId(i) if isinstance(i, str) else i for i in ids]
    return {str(u["_id"]): u["name"] async for u in get_db().users.find({"_id": {"$in": oids}})}


async def run_tool(name: str, args: dict, user: dict) -> dict:
    db = get_db()
    uid = user["_id"]
    if name == "search_roommates":
        me = await db.profiles.find_one({"user_id": uid})
        if not me:
            return {"error": "User has no profile yet."}
        extra = {k: args.get(k) for k in ("food", "smoking", "max_budget", "area") if args.get(k) not in (None, "")}
        matches = await compute_matches(me, extra, limit=5)
        return {"matches": [{"name": m["name"], "score": m["score"], "area": m["area"], "reasons": m["reasons"][:2]} for m in matches]}
    if name == "my_balances":
        room = await room_for(uid)
        if not room:
            return {"error": "User is not in a room yet."}
        s = await room_summary(room)
        names = await _names(list(s["balances"]))
        return {"payments": [{"from": names.get(p["from_user"]), "to": names.get(p["to_user"]), "amount": p["amount"]} for p in s["payments"]],
                "your_balance": s["balances"].get(str(uid), 0)}
    if name == "my_complaints":
        items = [c async for c in db.complaints.find({"raised_by": uid}).sort("created_at", -1).limit(10)]
        return {"complaints": [{"title": c["title"], "status": c["status"], "category": c["category"], "priority": c["priority"]} for c in items]}
    if name == "search_listings":
        q: dict = {"status": "available"}
        if args.get("category"):
            q["category"] = args["category"]
        if args.get("max_price"):
            q["price"] = {"$lte": float(args["max_price"])}
        if args.get("query"):
            q["title"] = {"$regex": re.escape(str(args["query"])), "$options": "i"}
        items = [x async for x in db.listings.find(q).limit(8)]
        return {"listings": [{"title": x["title"], "price": x["price"], "condition": x.get("condition"), "location": x.get("location")} for x in items]}
    if name == "hostel_rules":
        res = await rag.answer(user.get("hostel") or "default", str(args.get("question", "")), str(uid))
        return {"answer": res["answer"]}
    return {"error": f"Unknown tool {name}"}


SYSTEM = (
    "You are the Hostel/PG Life assistant for Indian students and young professionals. "
    "You can call tools to look up real data. Tools:\n"
    + "\n".join(f"- {k}: {v}" for k, v in TOOLS.items())
    + '\nReply with ONLY JSON: either {"tool": "<name>", "args": {...}} to call a tool, '
    'or {"answer": "<final answer for the user>"}. Use tool results; never invent people, prices or rules. '
    "Keep answers short and friendly. Amounts are in rupees (₹)."
)


async def ask(question: str, user: dict, history: list[dict] | None = None) -> dict:
    uid = str(user["_id"])
    steps = []
    if await _can_use_ai(uid):
        try:
            msgs = [{"role": "model" if m["role"] == "assistant" else "user", "text": m["text"]} for m in (history or [])[-6:]]
            msgs.append({"role": "user", "text": question})
            for _ in range(4):
                out = await llm.generate(msgs, system=SYSTEM, json_mode=True, temperature=0.2)
                if isinstance(out, dict) and out.get("answer"):
                    return {"answer": out["answer"], "steps": steps, "source": "gemini"}
                if isinstance(out, dict) and out.get("tool") in TOOLS:
                    result = await run_tool(out["tool"], out.get("args") or {}, user)
                    steps.append({"tool": out["tool"], "args": out.get("args") or {}})
                    msgs.append({"role": "model", "text": json.dumps(out)})
                    msgs.append({"role": "user", "text": f"Tool result: {json.dumps(result, default=str)[:4000]}"})
                    continue
                break
        except AIUnavailable:
            pass
    return await _offline(question, user, steps)


def _offline_intent(q: str) -> tuple[str, dict]:
    t = q.lower()
    if re.search(r"\b(owe|owes|balance|money|settle|pay|paid|split)\b", t):
        return "my_balances", {}
    if "complaint" in t or "ticket" in t:
        return "my_complaints", {}
    if re.search(r"\b(buy|sell|listing|market|second.?hand|cooler|book|cycle|chair|laptop|mattress)\b", t):
        args: dict = {}
        m = re.search(r"(?:under|below|less than|<)\s*(?:rs\.?|₹)?\s*(\d[\d,]*)", t)
        if m:
            args["max_price"] = int(m.group(1).replace(",", ""))
        for word in ("cooler", "book", "cycle", "chair", "laptop", "mattress", "table", "fan", "kettle"):
            if word in t:
                args["query"] = word
        return "search_listings", args
    if re.search(r"\b(rule|rules|gate|curfew|allowed|timing|visitor|warden|fine)\b", t):
        return "hostel_rules", {"question": q}
    args = {}
    if "non-veg" in t or "nonveg" in t or "non veg" in t:
        args["food"] = "nonveg"
    elif "veg" in t:
        args["food"] = "veg"
    if "non-smok" in t or "non smok" in t or "no smok" in t:
        args["smoking"] = False
    m = re.search(r"(?:under|below|budget|less than)\s*(?:rs\.?|₹)?\s*(\d[\d,]*)", t)
    if m:
        args["max_budget"] = int(m.group(1).replace(",", ""))
    m = re.search(r"\bin ([a-z ]+?)(?: under| below| with|$|,|\?)", t)
    if m and m.group(1).strip() not in ("the", "my", "a"):
        args["area"] = m.group(1).strip()
    return "search_roommates", args


async def _offline(question: str, user: dict, steps: list) -> dict:
    tool, args = _offline_intent(question)
    result = await run_tool(tool, args, user)
    steps.append({"tool": tool, "args": args})
    if "error" in result:
        answer = result["error"]
    elif tool == "search_roommates":
        ms = result["matches"]
        answer = "Top matches: " + "; ".join(f"{m['name']} ({m['score']}%, {m['area']})" for m in ms) if ms else "No matches for those filters yet."
    elif tool == "my_balances":
        ps = result["payments"]
        answer = "All settled up!" if not ps else "To settle up: " + "; ".join(f"{p['from']} pays {p['to']} ₹{p['amount']:.0f}" for p in ps)
    elif tool == "my_complaints":
        cs = result["complaints"]
        answer = "You have no complaints." if not cs else "Your complaints: " + "; ".join(f"{c['title']} ({c['status']})" for c in cs)
    elif tool == "search_listings":
        ls = result["listings"]
        answer = "Nothing listed for that right now." if not ls else "Found: " + "; ".join(f"{x['title']} for ₹{x['price']:.0f}" for x in ls)
    else:
        answer = result["answer"]
    return {"answer": answer, "steps": steps, "source": "offline"}
