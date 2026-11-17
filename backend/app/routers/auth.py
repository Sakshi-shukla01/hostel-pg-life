"""Accounts: sign-up with email verification code, login, forgot/reset password, Google sign-in."""
import logging
import re
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.config import get_settings
from app.db import clean, get_db
from app.security import create_token, get_current_user, hash_password, is_student_email, verify_password
from app.services import otp
from app.utils import now

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("auth")


def _strong(password: str) -> str:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password needs at least 8 characters, with letters and numbers")
    return password


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(max_length=100)
    role: Literal["student", "warden"] = "student"
    hostel: str = Field(default="default", max_length=60, description="Hostel/PG code shared by its residents")

    _pw = field_validator("password")(classmethod(lambda cls, v: _strong(v)))


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class CodeIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class ResendIn(BaseModel):
    email: EmailStr
    purpose: Literal["verify", "reset"] = "verify"


class ResetIn(CodeIn):
    new_password: str = Field(max_length=100)

    _pw = field_validator("new_password")(classmethod(lambda cls, v: _strong(v)))


class GoogleIn(BaseModel):
    credential: str = Field(min_length=20)
    role: Literal["student", "warden"] = "student"
    hostel: str = Field(default="default", max_length=60)


class MeIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    hostel: str | None = Field(default=None, min_length=1, max_length=60)


def _session(user: dict, **extra) -> dict:
    return {"token": create_token(str(user["_id"])), "user": clean(user), **extra}


def _pending(email: str, dev_code: str | None) -> dict:
    out = {"needs_verification": True, "email": email}
    if dev_code:
        out["dev_code"] = dev_code  # only in dev mode, when no SMTP is configured
    return out


@router.get("/config")
async def auth_config():
    """Tells the frontend which sign-in options are switched on."""
    s = get_settings()
    return {"google_client_id": s.google_client_id or None, "email_mode": "smtp" if s.email_enabled else "dev"}


@router.post("/register")
async def register(body: RegisterIn):
    db = get_db()
    email = body.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing and existing.get("email_verified", True):
        raise HTTPException(409, "An account with this email already exists. Log in instead.")
    fields = {
        "name": body.name.strip(), "email": email, "password_hash": hash_password(body.password), "role": body.role,
        "hostel": body.hostel.strip().lower() or "default", "verified": is_student_email(email),
        "email_verified": False, "auth_provider": "password",
    }
    if existing:  # signed up before but never verified: update details, send a new code
        await db.users.update_one({"_id": existing["_id"]}, {"$set": fields})
    else:
        await db.users.insert_one({**fields, "blocked": [], "created_at": now()})
    return _pending(email, await otp.send_code(email, body.name, "verify"))


@router.post("/verify-email")
async def verify_email(body: CodeIn):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user:
        raise HTTPException(404, "No account with this email. Sign up first.")
    if user.get("email_verified", True):
        raise HTTPException(400, "This email is already verified. Log in.")
    await otp.check_code(user["email"], "verify", body.code)
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"email_verified": True}})
    user["email_verified"] = True
    return _session(user)


@router.post("/resend-code")
async def resend_code(body: ResendIn):
    """Same answer whether or not the email exists, so nobody can check who has an account."""
    user = await get_db().users.find_one({"email": body.email.lower()})
    dev_code = None
    if user and (body.purpose == "reset" or not user.get("email_verified", True)):
        dev_code = await otp.send_code(user["email"], user["name"], body.purpose)
    out = {"sent": True}
    if dev_code:
        out["dev_code"] = dev_code
    return out


@router.post("/forgot-password")
async def forgot_password(body: ResendIn):
    return await resend_code(ResendIn(email=body.email, purpose="reset"))


@router.post("/reset-password")
async def reset_password(body: ResetIn):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user:
        raise HTTPException(400, "This code has expired. Ask for a new one.")
    await otp.check_code(user["email"], "reset", body.code)
    # Proving access to the inbox also verifies the email
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password), "email_verified": True}})
    user = await db.users.find_one({"_id": user["_id"]})
    return _session(user)


@router.post("/login")
async def login(body: LoginIn):
    user = await get_db().users.find_one({"email": body.email.lower()})
    if user and not user.get("password_hash"):
        raise HTTPException(400, "This account uses Google sign-in. Use “Continue with Google”, or set a password with “Forgot password”.")
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Wrong email or password")
    if not user.get("email_verified", True):
        raise HTTPException(403, "Verify your email to continue. We'll send you a new code.")
    return _session(user)


async def _google_identity(credential: str) -> dict:
    """Checks a Google ID token with Google's tokeninfo endpoint."""
    client_id = get_settings().google_client_id
    if not client_id:
        raise HTTPException(503, "Google sign-in is not set up. Add GOOGLE_CLIENT_ID to the backend .env.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": credential})
    except httpx.HTTPError:
        raise HTTPException(502, "Couldn't reach Google. Check your internet and try again.")
    if resp.status_code != 200:
        raise HTTPException(401, "Google sign-in failed. Please try again.")
    info = resp.json()
    if info.get("aud") != client_id or info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "This Google sign-in was made for a different app.")
    if str(info.get("email_verified")).lower() != "true":
        raise HTTPException(401, "Your Google email isn't verified.")
    return info


@router.post("/google")
async def google_sign_in(body: GoogleIn):
    info = await _google_identity(body.credential)
    db = get_db()
    email = info["email"].lower()
    user = await db.users.find_one({"email": email})
    is_new = user is None
    if is_new:
        user = {
            "name": info.get("name") or email.split("@")[0], "email": email, "password_hash": None, "role": body.role,
            "hostel": body.hostel.strip().lower() or "default", "verified": is_student_email(email), "email_verified": True,
            "auth_provider": "google", "google_sub": info.get("sub"), "picture": info.get("picture"), "blocked": [], "created_at": now(),
        }
        res = await db.users.insert_one(user)
        user["_id"] = res.inserted_id
    else:  # link Google to an existing account with the same (Google-verified) email
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"google_sub": info.get("sub"), "email_verified": True, "picture": info.get("picture")}})
        user = await db.users.find_one({"_id": user["_id"]})
    return _session(user, is_new=is_new)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return clean(user)


@router.patch("/me")
async def update_me(body: MeIn, user: dict = Depends(get_current_user)):
    changes = {k: v.strip() for k, v in body.model_dump(exclude_none=True).items()}
    if "hostel" in changes:
        changes["hostel"] = changes["hostel"].lower()
    if changes:
        await get_db().users.update_one({"_id": user["_id"]}, {"$set": changes})
    return clean(await get_db().users.find_one({"_id": user["_id"]}))
