"""Runs the matching engine against the database (used by the API and the AI agent)."""
from app.ai.features import best_pair
from app.db import get_db
from app.services import matching


async def active_weights() -> tuple[dict, str]:
    model = await get_db().ml_models.find_one({"active": True}, sort=[("trained_at", -1)])
    if model and model.get("weights"):
        return model["weights"], "learned"
    return matching.DEFAULT_WEIGHTS, "default"


async def compute_matches(me: dict, extra: dict | None = None, limit: int = 20) -> list[dict]:
    from app.config import get_settings

    db = get_db()
    extra = extra or {}
    weights, weight_source = await active_weights()
    hw = get_settings().habits_weight
    candidates = [p async for p in db.profiles.find({"city_key": me.get("city_key"), "user_id": {"$ne": me["user_id"]}})]
    users = {u["_id"]: u async for u in db.users.find({"_id": {"$in": [c["user_id"] for c in candidates]}})}

    results = []
    for other in candidates:
        if matching.hard_filter(me, other):
            continue
        oa = other.get("answers", {})
        if extra.get("food") and oa.get("food") != extra["food"]:
            continue
        if extra.get("smoking") is not None and bool(oa.get("smoking")) != bool(extra["smoking"]):
            continue
        if extra.get("max_budget") and other.get("budget_min", 0) > extra["max_budget"]:
            continue
        if extra.get("area") and extra["area"].lower() not in (other.get("area") or "").lower():
            continue

        scores = matching.factor_scores(me.get("answers", {}), oa)
        habits = matching.habits_score(scores, weights)
        u, v, source = best_pair(me, other)
        personality = matching.personality_score(matching.cosine(u, v), source)
        final = round(hw * habits + (1 - hw) * personality)
        reasons, conflicts = matching.explain(scores, me.get("answers", {}), oa, weights)
        user = users.get(other["user_id"], {})
        results.append({
            "user_id": str(other["user_id"]),
            "name": user.get("name", "Unknown"),
            "verified": user.get("verified", False),
            "college_or_office": other.get("college_or_office", ""),
            "area": other.get("area", ""),
            "budget_min": other.get("budget_min"),
            "budget_max": other.get("budget_max"),
            "bio": other.get("bio", ""),
            "interests": other.get("interests", []),
            "answers": oa,
            "score": final,
            "habits_score": round(habits),
            "personality_score": round(personality),
            "embedding_source": source,
            "weights_source": weight_source,
            "reasons": reasons,
            "conflicts": conflicts,
        })
    results.sort(key=lambda r: -r["score"])
    return results[:limit]
