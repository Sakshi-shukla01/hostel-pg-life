from app.ai import fallback
from app.ai.features import normalize, parse_answer
from app.services import matching, rag, splitting

NIGHT_OWL = {"sleep_time": "01:00", "wake_time": "08:30", "cleanliness": 4, "study_style": "silent", "food": "veg",
             "smoking": False, "drinking": False, "guests": 1, "noise": 2, "ac": "fan", "personality": "introvert"}
EARLY_BIRD = {"sleep_time": "22:00", "wake_time": "05:30", "cleanliness": 2, "study_style": "music", "food": "nonveg",
              "smoking": True, "drinking": True, "guests": 3, "noise": 5, "ac": "ac", "personality": "extrovert"}


def test_identical_habits_score_100():
    assert matching.habits_score(matching.factor_scores(NIGHT_OWL, NIGHT_OWL)) == 100


def test_opposites_score_low():
    assert matching.habits_score(matching.factor_scores(NIGHT_OWL, EARLY_BIRD)) < 25


def test_sleep_time_wraps_midnight():
    # 23:30 and 00:30 are one hour apart, not 23 hours
    assert matching.factor_scores({"sleep_time": "23:30"}, {"sleep_time": "00:30"})["sleep_time"] == 1.0


def test_weights_sum_to_100():
    assert sum(matching.DEFAULT_WEIGHTS.values()) == 100


def _p(uid, **kw):
    base = {"user_id": uid, "city": "Pune", "gender": "female", "gender_pref": "same", "budget_min": 6000,
            "budget_max": 9000, "move_in": "2026-12-01", "answers": dict(NIGHT_OWL), "dealbreakers": []}
    base.update(kw)
    return base


def test_hard_filters():
    me = _p(1)
    assert matching.hard_filter(me, _p(2)) is None
    assert matching.hard_filter(me, _p(2, city="Delhi")) == "different city"
    assert matching.hard_filter(me, _p(2, gender="male")) == "gender preference"
    assert matching.hard_filter(me, _p(2, budget_min=12000, budget_max=15000)) == "budget"
    assert matching.hard_filter(me, _p(2, move_in="2027-03-01")) == "move-in date"
    smoker = _p(2, answers={**NIGHT_OWL, "smoking": True})
    assert matching.hard_filter(_p(1, dealbreakers=["smoking"]), smoker).startswith("dealbreaker")


def test_explain_gives_reasons_and_conflicts():
    reasons, conflicts = matching.explain(matching.factor_scores(NIGHT_OWL, {**NIGHT_OWL, "ac": "ac"}), NIGHT_OWL, {**NIGHT_OWL, "ac": "ac"})
    assert any("sleep" in r.lower() for r in reasons)
    assert any("AC" in c for c in conflicts)


def test_split_and_simplify():
    shares = splitting.shares_for(100, ["a", "b", "c"])
    assert round(sum(shares.values()), 2) == 100
    expenses = [
        {"paid_by": "a", "amount": 900, "shares": splitting.shares_for(900, ["a", "b", "c"])},
        {"paid_by": "b", "amount": 300, "shares": splitting.shares_for(300, ["a", "b", "c"])},
    ]
    bal = splitting.balances(expenses)
    assert bal == {"a": 500.0, "b": -100.0, "c": -400.0}
    payments = splitting.simplify(bal)
    assert len(payments) == 2 and sum(p["amount"] for p in payments) == 500


def test_settlement_clears_balance():
    bal = splitting.balances([{"paid_by": "a", "amount": 200, "shares": {"a": 100, "b": 100}}],
                             [{"from_user": "b", "to_user": "a", "amount": 100}])
    assert splitting.simplify(bal) == []


def test_onboarding_parsing():
    assert parse_answer("sleep_time", "around 1 am") == "01:00"
    assert parse_answer("sleep_time", "11") == "23:00"
    assert parse_answer("wake_time", "7:30") == "07:30"
    assert parse_answer("food", "non veg") == "nonveg"
    assert parse_answer("smoking", "no never") is False
    assert parse_answer("drinking", "occasionally") is True
    assert parse_answer("guests", "sometimes") == 2
    assert parse_answer("personality", "bit of an introvert") == "introvert"
    assert normalize({"cleanliness": "4", "noise": 9, "food": "veg"}) == {"cleanliness": 4, "food": "veg"}


def test_local_embeddings_capture_shared_interests():
    a = fallback.embed("I love cricket and coding")
    b = fallback.embed("football and programming are my thing")
    c = fallback.embed("I enjoy painting and gardening")
    assert matching.cosine(a, b) > matching.cosine(a, c)


def test_complaint_classifier():
    r = fallback.classify_complaint("Bathroom tap is leaking all night")
    assert r["category"] == "plumbing"
    assert fallback.classify_complaint("sparks from the switch board")["priority"] == "high"


def test_moderation():
    assert fallback.moderate("Pay advance payment first then I'll send the cooler")["flagged"]
    assert not fallback.moderate("Is the cooler still available?")["flagged"]


def test_rag_chunking():
    text = "\n\n".join(f"{i}. Rule number {i} says something important about hostel life." for i in range(1, 40))
    chunks = rag.chunk(text, size=300)
    assert len(chunks) > 3 and all(len(c) <= 300 for c in chunks)
