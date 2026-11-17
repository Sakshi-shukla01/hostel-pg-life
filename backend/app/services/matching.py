"""Hybrid roommate matching.

final = habits_weight * habits_score + (1 - habits_weight) * personality_score

* Hard filters remove people who can never work (city, gender preference,
  budget, move-in date, dealbreakers).
* habits_score (0-100): weighted similarity of lifestyle answers.
* personality_score (0-100): cosine similarity of bio/interest embeddings.
* Weights start as hand-tuned defaults and can be replaced by weights the
  learning matcher (services/learner.py) fits on real roommate ratings.
"""
from datetime import date
import math

# Default weights (sum = 100). Sleep matters most: it causes the most fights.
DEFAULT_WEIGHTS: dict[str, float] = {
    "sleep_time": 20,
    "wake_time": 10,
    "cleanliness": 15,
    "study_style": 10,
    "food": 10,
    "smoking": 7,
    "drinking": 3,
    "guests": 8,
    "noise": 7,
    "ac": 5,
    "personality": 5,
}
FACTORS = list(DEFAULT_WEIGHTS)

LABELS = {
    "sleep_time": "sleep time",
    "wake_time": "wake-up time",
    "cleanliness": "cleanliness",
    "study_style": "study style",
    "food": "food habits",
    "smoking": "smoking",
    "drinking": "drinking",
    "guests": "having guests over",
    "noise": "noise and calls",
    "ac": "AC or fan",
    "personality": "social energy",
}


def _minutes(hhmm: str) -> int:
    h, m = (hhmm or "00:00").split(":")[:2]
    return int(h) * 60 + int(m)


def _time_gap(a: str, b: str) -> int:
    d = abs(_minutes(a) - _minutes(b))
    return min(d, 1440 - d)


def _time_score(a: str, b: str) -> float:
    gap = _time_gap(a, b)
    if gap <= 60:
        return 1.0
    if gap <= 120:
        return 0.5
    if gap <= 180:
        return 0.2
    return 0.0


def factor_scores(a: dict, b: dict) -> dict[str, float]:
    """Each factor scored 0..1. `a` and `b` are the `answers` dicts."""
    s: dict[str, float] = {}
    s["sleep_time"] = _time_score(a.get("sleep_time", "23:00"), b.get("sleep_time", "23:00"))
    s["wake_time"] = _time_score(a.get("wake_time", "07:00"), b.get("wake_time", "07:00"))
    s["cleanliness"] = 1 - abs(int(a.get("cleanliness", 3)) - int(b.get("cleanliness", 3))) / 4

    sa, sb = a.get("study_style", "silent"), b.get("study_style", "silent")
    s["study_style"] = 1.0 if sa == sb else (0.5 if "library" in (sa, sb) else 0.0)

    fa, fb = a.get("food", "veg"), b.get("food", "veg")
    if fa == fb:
        s["food"] = 1.0
    elif "flexible" in (fa, fb) or {fa, fb} == {"veg", "eggetarian"}:
        s["food"] = 0.5
    else:
        s["food"] = 0.0

    s["smoking"] = 1.0 if bool(a.get("smoking")) == bool(b.get("smoking")) else 0.0
    s["drinking"] = 1.0 if bool(a.get("drinking")) == bool(b.get("drinking")) else 0.0
    s["guests"] = 1 - abs(int(a.get("guests", 1)) - int(b.get("guests", 1))) / 3
    s["noise"] = 1 - abs(int(a.get("noise", 3)) - int(b.get("noise", 3))) / 4

    aa, ab = a.get("ac", "either"), b.get("ac", "either")
    s["ac"] = 1.0 if aa == ab or "either" in (aa, ab) else 0.0

    pa, pb = a.get("personality", "ambivert"), b.get("personality", "ambivert")
    s["personality"] = 1.0 if pa == pb else (0.5 if "ambivert" in (pa, pb) else 0.2)
    return s


def _dates_close(d1: str | None, d2: str | None, days: int = 30) -> bool:
    if not d1 or not d2:
        return True
    try:
        return abs((date.fromisoformat(d1) - date.fromisoformat(d2)).days) <= days
    except ValueError:
        return True


def hard_filter(me: dict, other: dict) -> str | None:
    """Return the reason they can't match, or None if they pass."""
    if me["user_id"] == other["user_id"]:
        return "same person"
    if (me.get("city") or "").strip().lower() != (other.get("city") or "").strip().lower():
        return "different city"
    for x, y in ((me, other), (other, me)):
        if x.get("gender_pref", "same") == "same" and x.get("gender") != y.get("gender"):
            return "gender preference"
    if me.get("budget_max", 10**9) < other.get("budget_min", 0) or other.get("budget_max", 10**9) < me.get("budget_min", 0):
        return "budget"
    if not _dates_close(me.get("move_in"), other.get("move_in")):
        return "move-in date"
    scores = factor_scores(me.get("answers", {}), other.get("answers", {}))
    for x in (me, other):
        for key in x.get("dealbreakers", []):
            if key in scores and scores[key] < 1.0:
                return f"dealbreaker: {LABELS.get(key, key)}"
    return None


def habits_score(scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    total = sum(w.values()) or 1
    return 100 * sum(w[k] * scores[k] for k in FACTORS) / total


def cosine(u: list[float] | None, v: list[float] | None) -> float | None:
    if not u or not v or len(u) != len(v):
        return None
    dot = sum(a * b for a, b in zip(u, v))
    nu = math.sqrt(sum(a * a for a in u))
    nv = math.sqrt(sum(b * b for b in v))
    if nu == 0 or nv == 0:
        return None
    return dot / (nu * nv)


# Raw cosine ranges differ by embedding model, so we rescale to 0..100.
CALIBRATION = {"gemini": (0.55, 0.90), "local": (-0.05, 0.60)}


def personality_score(cos: float | None, source: str) -> float:
    if cos is None:
        return 50.0
    lo, hi = CALIBRATION.get(source, (0.0, 1.0))
    return round(100 * min(1.0, max(0.0, (cos - lo) / (hi - lo))), 1)


def explain(scores: dict[str, float], a: dict, b: dict, weights: dict | None = None) -> tuple[list[str], list[str]]:
    w = weights or DEFAULT_WEIGHTS
    reasons, conflicts = [], []
    ordered = sorted(FACTORS, key=lambda k: -w[k])
    for k in ordered:
        if scores[k] >= 0.99 and w[k] >= 7:
            reasons.append(_reason_text(k, a))
        elif scores[k] <= 0.25:
            conflicts.append(_conflict_text(k, a, b))
    return reasons[:4], conflicts[:3]


def _reason_text(k: str, a: dict) -> str:
    if k == "sleep_time":
        return f"Similar sleep time (around {a.get('sleep_time')})"
    if k == "wake_time":
        return f"Both wake up around {a.get('wake_time')}"
    if k == "food":
        return f"Same food habits ({a.get('food')})"
    if k == "smoking":
        return "Both smokers" if a.get("smoking") else "Both non-smokers"
    if k == "study_style":
        return f"Same study style ({a.get('study_style')})"
    if k == "cleanliness":
        return "Same cleanliness level"
    return f"Match on {LABELS[k]}"


def _conflict_text(k: str, a: dict, b: dict) -> str:
    if k in ("sleep_time", "wake_time"):
        return f"Different {LABELS[k]}: you {a.get(k)}, they {b.get(k)}"
    if k in ("cleanliness", "guests", "noise"):
        return f"Different {LABELS[k]} levels: you {a.get(k)}, they {b.get(k)}"
    va, vb = a.get(k), b.get(k)
    if isinstance(va, bool):
        va, vb = ("yes" if va else "no"), ("yes" if vb else "no")
    return f"Different {LABELS[k]}: you {va}, they {vb}"


def feature_vector(scores: dict[str, float], cos_score: float) -> list[float]:
    """Used by the learning matcher: factor scores + personality (0..1)."""
    return [scores[k] for k in FACTORS] + [cos_score / 100]
