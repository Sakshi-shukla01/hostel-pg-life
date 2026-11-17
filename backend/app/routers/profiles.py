from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.ai import features
from app.db import clean, get_db
from app.security import get_current_user
from app.services.matching import FACTORS
from app.utils import now

router = APIRouter(tags=["profile"])


class Answers(BaseModel):
    sleep_time: str = Field(default="23:30", pattern=r"^\d{2}:\d{2}$")
    wake_time: str = Field(default="07:30", pattern=r"^\d{2}:\d{2}$")
    study_style: Literal["silent", "music", "library"] = "silent"
    cleanliness: int = Field(default=3, ge=1, le=5)
    food: Literal["veg", "nonveg", "eggetarian", "flexible"] = "veg"
    smoking: bool = False
    drinking: bool = False
    guests: int = Field(default=1, ge=0, le=3)
    noise: int = Field(default=3, ge=1, le=5)
    ac: Literal["ac", "fan", "either"] = "either"
    personality: Literal["introvert", "ambivert", "extrovert"] = "ambivert"


class ProfileIn(BaseModel):
    city: str = Field(min_length=2, max_length=60)
    area: str = Field(default="", max_length=80)
    gender: Literal["male", "female", "other"]
    gender_pref: Literal["same", "any"] = "same"
    budget_min: int = Field(ge=0, le=200000)
    budget_max: int = Field(ge=0, le=200000)
    move_in: str | None = None
    room_type: Literal["2-sharing", "3-sharing", "flat"] = "2-sharing"
    college_or_office: str = Field(default="", max_length=100)
    bio: str = Field(default="", max_length=600)
    interests: list[str] = Field(default_factory=list, max_length=15)
    answers: Answers = Field(default_factory=Answers)
    dealbreakers: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("dealbreakers")
    @classmethod
    def known_factors(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in FACTORS]
        if bad:
            raise ValueError(f"Unknown dealbreakers: {bad}")
        return v


@router.put("/profile")
async def save_profile(body: ProfileIn, user: dict = Depends(get_current_user)):
    if body.budget_max < body.budget_min:
        raise HTTPException(400, "Max budget must be at least the min budget")
    data = body.model_dump()
    data.update({"user_id": user["_id"], "city_key": body.city.strip().lower(), "updated_at": now()})
    data.update(await features.embeddings_for(features.profile_text(data), str(user["_id"])))
    await get_db().profiles.update_one({"user_id": user["_id"]}, {"$set": data}, upsert=True)
    return clean(await get_db().profiles.find_one({"user_id": user["_id"]}))


@router.get("/profile/me")
async def my_profile(user: dict = Depends(get_current_user)):
    return clean(await get_db().profiles.find_one({"user_id": user["_id"]}))


class OnboardingIn(BaseModel):
    history: list[dict] = Field(default_factory=list, max_length=60)
    profile: dict = Field(default_factory=dict)


@router.post("/ai/onboarding")
async def onboarding(body: OnboardingIn, user: dict = Depends(get_current_user)):
    """One turn of the AI onboarding chat. Returns the next question and the answers collected so far."""
    history = [{"role": m.get("role", "user"), "text": str(m.get("text", ""))[:1000]} for m in body.history]
    return await features.onboarding_turn(history, body.profile, str(user["_id"]))
