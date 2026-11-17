"""Learning matcher: fits new factor weights from real roommate ratings.

Each rating (1-5 stars after living together) becomes one training row:
features = the 11 factor scores + personality score, label = stars >= 4.
A logistic regression learns which factors actually predict a happy pair;
its positive coefficients become the new weights (normalised to 100).
"""
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app.ai.features import best_pair
from app.db import get_db
from app.services import matching

MIN_RATINGS = 12


async def build_dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    db = get_db()
    X, y, baseline = [], [], []
    async for r in db.ratings.find({}):
        a = await db.profiles.find_one({"user_id": r["from_user"]})
        b = await db.profiles.find_one({"user_id": r["to_user"]})
        if not a or not b:
            continue
        scores = matching.factor_scores(a.get("answers", {}), b.get("answers", {}))
        u, v, src = best_pair(a, b)
        pers = matching.personality_score(matching.cosine(u, v), src)
        X.append(matching.feature_vector(scores, pers))
        y.append(1 if r["stars"] >= 4 else 0)
        baseline.append(matching.habits_score(scores))
    return np.array(X), np.array(y), np.array(baseline)


async def train() -> dict:
    X, y, baseline = await build_dataset()
    if len(y) < MIN_RATINGS or len(set(y)) < 2:
        return {"trained": False, "message": f"Need at least {MIN_RATINGS} ratings with both happy and unhappy pairs (have {len(y)})."}

    model = LogisticRegression(max_iter=1000, C=1.0)
    folds = max(2, min(5, int(min(np.bincount(y)))))
    probs = cross_val_predict(model, X, y, cv=StratifiedKFold(folds, shuffle=True, random_state=7), method="predict_proba")[:, 1]
    learned_auc = float(roc_auc_score(y, probs))
    default_auc = float(roc_auc_score(y, baseline))
    model.fit(X, y)

    coefs = model.coef_[0][: len(matching.FACTORS)]
    # Normalise positive coefficients to 100, then blend 50/50 with the defaults so a
    # factor people rarely complain about (but still care about) never drops to zero.
    raw = np.clip(coefs, 0, None) + 1e-6
    learned = 100 * raw / raw.sum()
    weights = {k: round(0.5 * float(w) + 0.5 * matching.DEFAULT_WEIGHTS[k], 2) for k, w in zip(matching.FACTORS, learned)}

    doc = {
        "weights": weights,
        "n_ratings": int(len(y)),
        "learned_auc": round(learned_auc, 3),
        "default_auc": round(default_auc, 3),
        "active": learned_auc >= default_auc,  # only switch if it is actually better
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    db = get_db()
    if doc["active"]:
        await db.ml_models.update_many({}, {"$set": {"active": False}})
    await db.ml_models.insert_one(doc)
    doc.pop("_id", None)
    return {"trained": True, **doc}
