"""AI features used by the routers. Each one tries Gemini first and falls
back to the offline version, and reports which one answered via `source`."""
import json
import logging
import re

from app.ai import fallback, llm
from app.ai.llm import AIUnavailable
from app.services.limits import allow_ai_call, cache_get, cache_set

log = logging.getLogger("ai")


async def _can_use_ai(user_id: str | None) -> bool:
    from app.config import get_settings

    if not get_settings().ai_enabled:
        return False
    return await allow_ai_call(user_id or "anon")


# ---------------------------------------------------------------- embeddings
def profile_text(p: dict) -> str:
    a = p.get("answers", {})
    interests = ", ".join(p.get("interests", []))
    return f"{p.get('bio', '')}. Interests: {interests}. Personality: {a.get('personality', '')}."


async def embeddings_for(text: str, user_id: str | None = None) -> dict:
    """Always store the local vector; add the Gemini vector when available.
    Comparisons use Gemini vectors when both sides have them, else local ones."""
    out = {"emb_local": fallback.embed(text), "emb_gemini": None}
    if text.strip() and await _can_use_ai(user_id):
        try:
            out["emb_gemini"] = await llm.embed(text)
        except AIUnavailable as exc:
            log.info("embed fallback: %s", exc)
    return out


def best_pair(a: dict, b: dict) -> tuple[list[float] | None, list[float] | None, str]:
    if a.get("emb_gemini") and b.get("emb_gemini"):
        return a["emb_gemini"], b["emb_gemini"], "gemini"
    return a.get("emb_local"), b.get("emb_local"), "local"


# ---------------------------------------------------------------- onboarding
QUESTIONS = [
    ("sleep_time", "Hi! I'm your Hostel/PG Life assistant. Let's build your roommate profile. What time do you usually go to sleep?"),
    ("wake_time", "And what time do you usually wake up?"),
    ("study_style", "How do you like to study: in silence, with music, or mostly in the library?"),
    ("cleanliness", "On a scale of 1 to 5, how tidy are you? (1 = messy, 5 = very neat)"),
    ("food", "What do you eat: veg, non-veg, eggetarian, or flexible?"),
    ("smoking", "Do you smoke?"),
    ("drinking", "Do you drink alcohol?"),
    ("guests", "How often do you have friends over: never, rarely, sometimes, or often?"),
    ("noise", "How loud are you with calls, music or gaming, from 1 (very quiet) to 5 (loud)?"),
    ("ac", "AC or fan? Or are you fine with either?"),
    ("personality", "Would you call yourself an introvert, an extrovert, or somewhere in between?"),
    ("bio", "Last one: tell me a bit about yourself and your interests (hobbies, what you study or work on)."),
]
FIELDS = [k for k, _ in QUESTIONS]


def _parse_time(text: str, kind: str) -> str | None:
    t = text.lower()
    if "midnight" in t:
        return "00:00"
    if "noon" in t:
        return "12:00"
    m = re.search(r"(\d{1,2})(?::|\.)?(\d{2})?\s*(am|pm|a\.m|p\.m)?", t)
    if not m:
        return None
    h, mins, suffix = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").replace(".", "")
    if h > 23 or mins > 59:
        return None
    if suffix == "pm" and h < 12:
        h += 12
    elif suffix == "am" and h == 12:
        h = 0
    elif not suffix and kind == "sleep" and 6 <= h <= 11:
        h += 12  # "sleep at 11" means 11 PM
    return f"{h:02d}:{mins:02d}"


def _parse_scale(text: str, words: dict[str, int]) -> int | None:
    m = re.search(r"\b([1-5])\b", text)
    if m:
        return int(m.group(1))
    t = text.lower()
    for w, v in words.items():
        if w in t:
            return v
    return None


def _yes(text: str) -> bool:
    t = text.lower()
    if re.search(r"\b(no|never|nahi|nope|dont|don't|not)\b", t):
        return False
    return bool(re.search(r"\b(yes|yeah|yup|haan|sometimes|occasionally|socially|regularly)\b", t))


def parse_answer(field: str, text: str):
    t = text.lower()
    if field == "sleep_time":
        return _parse_time(text, "sleep")
    if field == "wake_time":
        return _parse_time(text, "wake")
    if field == "study_style":
        return "music" if "music" in t else "library" if "library" in t else "silent"
    if field == "cleanliness":
        return _parse_scale(text, {"very neat": 5, "very clean": 5, "neat": 4, "clean": 4, "average": 3, "okay": 3, "messy": 2, "very messy": 1})
    if field == "food":
        if "non" in t:
            return "nonveg"
        if "egg" in t:
            return "eggetarian"
        if any(w in t for w in ("flex", "any", "both", "everything")):
            return "flexible"
        return "veg" if "veg" in t else None
    if field in ("smoking", "drinking"):
        return _yes(text)
    if field == "guests":
        for w, v in (("never", 0), ("rare", 1), ("some", 2), ("often", 3), ("daily", 3), ("frequent", 3)):
            if w in t:
                return v
        m = re.search(r"\b([0-3])\b", t)
        return int(m.group(1)) if m else None
    if field == "noise":
        return _parse_scale(text, {"very quiet": 1, "quiet": 2, "normal": 3, "loud": 5})
    if field == "ac":
        if "either" in t or "both" in t or "any" in t:
            return "either"
        return "ac" if re.search(r"\bac\b", t) else "fan" if "fan" in t else "either"
    if field == "personality":
        return "introvert" if "intro" in t else "extrovert" if "extro" in t else "ambivert"
    if field == "bio":
        return text.strip()[:600] or None
    return None


def normalize(profile: dict) -> dict:
    """Coerce model output into valid values; drop anything invalid."""
    out = {}
    for field in FIELDS:
        if field not in profile or profile[field] in (None, ""):
            continue
        v = profile[field]
        if field in ("sleep_time", "wake_time") and isinstance(v, str) and re.fullmatch(r"\d{2}:\d{2}", v):
            out[field] = v
        elif field in ("cleanliness", "noise") and str(v).isdigit() and 1 <= int(v) <= 5:
            out[field] = int(v)
        elif field == "guests" and str(v).isdigit() and 0 <= int(v) <= 3:
            out[field] = int(v)
        elif field in ("smoking", "drinking"):
            out[field] = v if isinstance(v, bool) else _yes(str(v))
        elif field == "bio":
            out[field] = str(v)[:600]
        else:
            parsed = parse_answer(field, str(v))
            if parsed is not None:
                out[field] = parsed
    return out


def _next_missing(profile: dict) -> str | None:
    return next((f for f in FIELDS if f not in profile), None)


ONBOARDING_SYSTEM = f"""You are a friendly assistant helping an Indian student or young professional
set up a roommate-matching profile for a hostel or PG. Ask ONE short question at a time,
in simple English (a little Hinglish is fine if the user uses it). Collect these fields:
sleep_time (HH:MM 24h), wake_time (HH:MM 24h), study_style (silent|music|library),
cleanliness (1-5), food (veg|nonveg|eggetarian|flexible), smoking (true/false), drinking (true/false),
guests (0=never,1=rarely,2=sometimes,3=often), noise (1-5), ac (ac|fan|either),
personality (introvert|ambivert|extrovert), bio (a short paragraph about them and their interests).
Return ONLY JSON: {{"reply": "<your next message>", "profile": {{<every field you know so far>}}, "done": <true when all fields are known>}}.
Field order to ask in: {", ".join(FIELDS)}."""


async def onboarding_turn(history: list[dict], profile: dict, user_id: str) -> dict:
    """history: [{"role": "user"|"assistant", "text": str}], profile: answers so far."""
    profile = normalize(profile or {})
    if await _can_use_ai(user_id):
        try:
            msgs = [{"role": "model" if m["role"] == "assistant" else "user", "text": m["text"]} for m in history]
            msgs.append({"role": "user", "text": f"(Profile so far: {json.dumps(profile)}) Continue."})
            data = await llm.generate(msgs, system=ONBOARDING_SYSTEM, json_mode=True, temperature=0.4)
            merged = {**profile, **normalize(data.get("profile", {}))}
            done = _next_missing(merged) is None
            reply = data.get("reply") or ("All set! Your profile is ready." if done else dict(QUESTIONS)[_next_missing(merged)])
            return {"reply": reply, "profile": merged, "done": done, "source": "gemini"}
        except (AIUnavailable, AttributeError, TypeError) as exc:
            log.info("onboarding fallback: %s", exc)

    # Offline: the latest user message answers the first missing field.
    asked = _next_missing(profile)
    last_user = next((m["text"] for m in reversed(history) if m["role"] == "user"), None)
    retry = False
    if asked and last_user and history and history[-1]["role"] == "user":
        value = parse_answer(asked, last_user)
        if value is None:
            retry = True
        else:
            profile[asked] = value
    nxt = _next_missing(profile)
    if nxt is None:
        return {"reply": "All set! Your profile is ready. Save it to see your matches.", "profile": profile, "done": True, "source": "offline"}
    q = dict(QUESTIONS)[nxt]
    if retry:
        q = "Sorry, I didn't get that. " + q.split("profile. ")[-1]
    return {"reply": q, "profile": profile, "done": False, "source": "offline"}


# ---------------------------------------------------------------- match summary
async def match_summary(me: dict, other: dict, reasons: list[str], conflicts: list[str], user_id: str) -> dict:
    key = f"summary:{me['user_id']}:{other['user_id']}:{me.get('updated_at')}:{other.get('updated_at')}"
    cached = await cache_get(key)
    if cached:
        return cached
    result = None
    if await _can_use_ai(user_id):
        prompt = (
            "Two people may share a hostel/PG room. In 2-3 friendly sentences, tell person A why they could "
            "get along with person B and one thing they should agree on before moving in. Address A as 'you'. "
            f"\nA habits: {json.dumps(me.get('answers', {}))}\nA bio: {me.get('bio', '')}"
            f"\nB name: {other.get('name', 'They')}\nB habits: {json.dumps(other.get('answers', {}))}\nB bio: {other.get('bio', '')}"
            f"\nComputed matches: {reasons}\nComputed conflicts: {conflicts}"
        )
        try:
            result = {"text": await llm.generate(prompt, temperature=0.6), "source": "gemini"}
        except AIUnavailable:
            pass
    if result is None:
        first = other.get("name", "They").split(" ")[0]
        good = ", ".join(r.lower() for r in reasons[:2]) or "a few habits in common"
        talk = conflicts[0].split(":")[0].lower() if conflicts else "how you split chores and bills"
        interest_words = set(fallback.SYNONYMS.values()) - {"introvert", "extrovert"}
        shared = set(fallback.tokens(" ".join(me.get("interests", [])) + " " + me.get("bio", ""))) & set(
            fallback.tokens(" ".join(other.get("interests", [])) + " " + other.get("bio", ""))
        ) & interest_words
        extra = f" You both seem into {', '.join(sorted(shared)[:2])}." if shared else ""
        result = {"text": f"You and {first} share {good}.{extra} Before moving in, agree on {talk}.", "source": "offline"}
    await cache_set(key, result)
    return result


# ---------------------------------------------------------------- moderation
async def moderate(text: str, user_id: str | None = None, use_llm: bool = False) -> dict:
    quick = fallback.moderate(text)
    if quick["flagged"] or not use_llm or not await _can_use_ai(user_id):
        return {**quick, "source": "offline"}
    try:
        data = await llm.generate(
            "You moderate a student marketplace and roommate app in India. Is this text a scam, abusive, "
            "or unsafe? Return JSON {\"flagged\": bool, \"reason\": str}. Text: " + text[:2000],
            json_mode=True, temperature=0,
        )
        return {"flagged": bool(data.get("flagged")), "reason": str(data.get("reason", "")), "source": "gemini"}
    except (AIUnavailable, AttributeError):
        return {**quick, "source": "offline"}


# ---------------------------------------------------------------- complaints
CATEGORIES = ["electrical", "plumbing", "wifi", "mess", "cleanliness", "furniture", "safety", "other"]


async def classify_complaint(text: str, image: tuple[bytes, str] | None, user_id: str) -> dict:
    if await _can_use_ai(user_id):
        try:
            data = await llm.generate(
                "A student raised a hostel/PG maintenance complaint. Using the text and the photo if given, return JSON "
                f'{{"category": one of {CATEGORIES}, "priority": "low"|"medium"|"high", "summary": "one clear sentence for the warden"}}. '
                f"High priority = safety risk or no water/power. Text: {text}",
                json_mode=True, temperature=0, image=image,
            )
            cat = data.get("category") if data.get("category") in CATEGORIES else fallback.classify_complaint(text)["category"]
            pri = data.get("priority") if data.get("priority") in ("low", "medium", "high") else "medium"
            return {"category": cat, "priority": pri, "summary": str(data.get("summary") or text)[:200], "source": "gemini"}
        except (AIUnavailable, AttributeError):
            pass
    return {**fallback.classify_complaint(text), "source": "offline"}


# ---------------------------------------------------------------- marketplace
LISTING_CATS = ["books", "electronics", "appliances", "furniture", "cycles", "other"]


async def autofill_listing(hint: str, image: tuple[bytes, str] | None, user_id: str) -> dict:
    if image and await _can_use_ai(user_id):
        try:
            data = await llm.generate(
                "A student in India wants to sell this used item to other students. From the photo"
                f" (and hint: '{hint}'), return JSON {{\"title\": str, \"category\": one of {LISTING_CATS}, "
                '"condition": "new"|"like new"|"good"|"fair", "description": "2 short sentences", '
                '"suggested_price": integer rupees for a fair second-hand student price}.',
                json_mode=True, temperature=0.3, image=image,
            )
            cat = data.get("category") if data.get("category") in LISTING_CATS else "other"
            return {
                "title": str(data.get("title", hint))[:80],
                "category": cat,
                "condition": data.get("condition", "good"),
                "description": str(data.get("description", ""))[:400],
                "suggested_price": int(data.get("suggested_price") or fallback.suggest_price(cat)),
                "source": "gemini",
            }
        except (AIUnavailable, ValueError, TypeError, AttributeError):
            pass
    cat = fallback.categorize_listing(hint)
    return {
        "title": hint.strip().title()[:80],
        "category": cat,
        "condition": "good",
        "description": f"Used {hint.strip().lower()} in good condition. Pick up from hostel.",
        "suggested_price": fallback.suggest_price(cat, "good"),
        "source": "offline",
    }


# ---------------------------------------------------------------- bill scanner
EXPENSE_CATS = ["rent", "electricity", "wifi", "groceries", "maid", "water", "gas", "food", "other"]


async def scan_bill(image: tuple[bytes, str], user_id: str) -> dict:
    if not await _can_use_ai(user_id):
        raise AIUnavailable("Bill scanning needs a free GEMINI_API_KEY. You can still add the expense by hand.")
    data = await llm.generate(
        "Read this Indian bill or receipt. Return JSON {\"title\": short name like 'Electricity - March', "
        f"\"amount\": total payable as a number, \"category\": one of {EXPENSE_CATS}, \"date\": \"YYYY-MM-DD\" or null}}.",
        json_mode=True, temperature=0, image=image,
    )
    try:
        amount = float(str(data.get("amount", "0")).replace(",", "").replace("₹", ""))
    except ValueError:
        amount = 0.0
    cat = data.get("category") if data.get("category") in EXPENSE_CATS else "other"
    return {"title": str(data.get("title", "Bill"))[:80], "amount": round(amount, 2), "category": cat, "date": data.get("date"), "source": "gemini"}


# ---------------------------------------------------------------- roommate agreement
async def roommate_agreement(profiles: list[dict], user_id: str) -> dict:
    if await _can_use_ai(user_id):
        try:
            text = await llm.generate(
                "Write a short, fair roommate agreement (6-8 numbered rules, simple English) for these hostel/PG "
                "roommates, based on their habits. Cover quiet hours, guests, cleaning, AC, food, shared costs. "
                + json.dumps([{"name": p.get("name"), "habits": p.get("answers", {})} for p in profiles]),
                temperature=0.4,
            )
            return {"text": text, "source": "gemini"}
        except AIUnavailable:
            pass
    answers = [p.get("answers", {}) for p in profiles]
    sleeps = sorted((a.get("sleep_time", "23:00") for a in answers), key=lambda t: (int(t[:2]) + 12) % 24)
    quiet = sleeps[0] if sleeps else "23:00"
    guests = min((a.get("guests", 1) for a in answers), default=1)
    guest_rule = {0: "No overnight guests; day visitors only with a heads-up.", 1: "Guests rarely, always tell roommates a day before.",
                  2: "Guests allowed a few times a month; no overnight stays without agreement.", 3: "Guests are fine, but not during quiet hours."}[guests]
    ac_rule = "Use the AC at night only if everyone agrees; otherwise fan." if len({a.get("ac") for a in answers} - {"either"}) > 1 else "AC/fan as everyone prefers."
    veg = any(a.get("food") == "veg" for a in answers) and any(a.get("food") == "nonveg" for a in answers)
    rules = [
        f"Quiet hours start at {quiet}: calls and music on headphones after that.",
        guest_rule,
        "Cleaning follows the weekly chore rotation in the app.",
        ac_rule,
        "Keep non-veg food in a separate, closed box." if veg else "Shared food only after asking.",
        "Shared bills are added in the app within 2 days and settled by the 5th of each month.",
        "Ask before using someone else's things (iron, charger, bucket).",
        "Any problem gets discussed calmly, face to face, within a day.",
    ]
    return {"text": "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1)), "source": "offline"}
