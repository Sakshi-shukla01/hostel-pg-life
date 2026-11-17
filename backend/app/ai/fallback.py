"""Offline AI fallbacks: used when no API key is set or the API fails.

They are simple on purpose (keyword rules, hashing embeddings) but give
sensible results, so the whole app can be demoed without internet.
"""
import hashlib
import math
import re

# Words that mean the same interest are mapped to one token, so
# "cricket" and "football" both count as "sports".
SYNONYMS = {
    "cricket": "sports", "football": "sports", "badminton": "sports", "gym": "fitness",
    "workout": "fitness", "yoga": "fitness", "running": "fitness",
    "coding": "tech", "programming": "tech", "developer": "tech", "dsa": "tech", "ai": "tech",
    "movies": "films", "netflix": "films", "series": "films", "anime": "films",
    "guitar": "music", "singing": "music", "songs": "music",
    "reading": "books", "novels": "books",
    "gaming": "games", "pubg": "games", "bgmi": "games", "valorant": "games",
    "quiet": "introvert", "shy": "introvert", "calm": "introvert",
    "party": "extrovert", "outgoing": "extrovert", "social": "extrovert",
    "cooking": "food", "foodie": "food",
    "travel": "travel", "trekking": "travel",
}
STOP = set("i am a an the and or but to of in on for with my me is are it this that very really love like enjoy".split())
DIM = 256


def _stem(w: str) -> str:
    """Tiny stemmer so 'visitors' == 'visitor' and 'closes' == 'close'."""
    for suffix in ("ing", "es", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [SYNONYMS.get(w, _stem(w)) for w in words if w not in STOP and len(w) > 1]


def embed(text: str) -> list[float]:
    """Hashing-trick bag-of-words vector, L2 normalised."""
    vec = [0.0] * DIM
    for tok in tokens(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % DIM] += 1.0 if (h >> 8) % 2 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


COMPLAINT_KEYWORDS = {
    "electrical": ["fan", "light", "bulb", "switch", "socket", "power", "electric", "wire", "ac", "geyser"],
    "plumbing": ["tap", "water", "leak", "pipe", "toilet", "flush", "drain", "bathroom", "shower"],
    "wifi": ["wifi", "wi-fi", "internet", "network", "router", "slow"],
    "mess": ["food", "mess", "meal", "dinner", "lunch", "breakfast", "stale"],
    "cleanliness": ["dirty", "clean", "garbage", "dust", "smell", "cockroach", "rat", "pest"],
    "furniture": ["bed", "chair", "table", "cupboard", "door", "window", "lock"],
    "safety": ["theft", "stolen", "harass", "unsafe", "fight", "fire"],
}
URGENT_WORDS = ["fire", "shock", "spark", "flood", "harass", "unsafe", "theft", "stolen", "no water", "emergency"]


def classify_complaint(text: str) -> dict:
    t = text.lower()
    scores = {cat: sum(w in t for w in words) for cat, words in COMPLAINT_KEYWORDS.items()}
    category = max(scores, key=scores.get) if max(scores.values()) > 0 else "other"
    if any(w in t for w in URGENT_WORDS) or category == "safety":
        priority = "high"
    elif category in ("plumbing", "electrical", "wifi"):
        priority = "medium"
    else:
        priority = "low"
    return {"category": category, "priority": priority, "summary": text.strip()[:140]}


LISTING_CATEGORIES = {
    "books": ["book", "novel", "notes", "guide", "textbook"],
    "electronics": ["laptop", "phone", "charger", "speaker", "headphone", "monitor", "keyboard", "mouse", "calculator"],
    "appliances": ["cooler", "fan", "kettle", "iron", "heater", "fridge", "induction"],
    "furniture": ["chair", "table", "mattress", "shelf", "rack", "bed"],
    "cycles": ["cycle", "bicycle", "bike"],
}
BASE_PRICE = {"books": 250, "electronics": 1500, "appliances": 1800, "furniture": 900, "cycles": 2500, "other": 500}
CONDITION_FACTOR = {"new": 0.8, "like new": 0.65, "good": 0.5, "fair": 0.35}


def categorize_listing(title: str) -> str:
    t = title.lower()
    for cat, words in LISTING_CATEGORIES.items():
        if any(w in t for w in words):
            return cat
    return "other"


def suggest_price(category: str, condition: str = "good") -> int:
    return int(round(BASE_PRICE.get(category, 500) * CONDITION_FACTOR.get(condition, 0.5) * 2 / 50) * 50)


BAD_WORDS = ["idiot", "stupid", "bastard", "kill you", "fuck", "bitch", "chutiya", "madarchod", "bhenchod"]
SCAM_SIGNS = ["advance payment", "pay first", "send otp", "share otp", "gift card", "western union", "upi pin"]


def moderate(text: str) -> dict:
    t = text.lower()
    if any(w in t for w in SCAM_SIGNS):
        return {"flagged": True, "reason": "Looks like a possible scam (asks for advance money, OTP or PIN)."}
    if any(w in t for w in BAD_WORDS):
        return {"flagged": True, "reason": "Message contains abusive language."}
    return {"flagged": False, "reason": ""}
