"""One-time codes for email verification and password reset.

* 6 digits, valid for 10 minutes, stored only as a keyed hash (never in plain text)
* max 5 wrong tries, then a new code is needed
* a new code can be requested once every 60 seconds
"""
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Literal

from fastapi import HTTPException

from app.config import get_settings
from app.db import get_db
from app.services.mailer import code_email, send_email
from app.utils import now

Purpose = Literal["verify", "reset"]
TTL = timedelta(minutes=10)
COOLDOWN = timedelta(seconds=60)
MAX_TRIES = 5


def _hash(email: str, purpose: str, code: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"{email}:{purpose}:{code}".encode(), hashlib.sha256).hexdigest()


async def send_code(email: str, name: str, purpose: Purpose) -> str | None:
    """Creates and emails a code. Returns the code only in dev mode (no SMTP, SHOW_DEV_CODES on)."""
    db = get_db()
    email = email.lower()
    existing = await db.otps.find_one({"email": email, "purpose": purpose})
    if existing and now() - existing["created_at"] < COOLDOWN:
        wait = int((COOLDOWN - (now() - existing["created_at"])).total_seconds()) + 1
        raise HTTPException(429, f"Please wait {wait} seconds before asking for a new code")
    code = f"{secrets.randbelow(10**6):06d}"
    await db.otps.update_one(
        {"email": email, "purpose": purpose},
        {"$set": {"code_hash": _hash(email, purpose, code), "created_at": now(), "expires_at": now() + TTL, "tries": 0}},
        upsert=True,
    )
    subject, text, html = code_email(name.split(" ")[0], code, purpose)
    try:
        sent = await send_email(email, subject, text, html)
    except Exception:
        raise HTTPException(502, "We couldn't send the email. Check the SMTP settings and try again.")
    s = get_settings()
    return code if (not sent and s.show_dev_codes) else None


async def check_code(email: str, purpose: Purpose, code: str) -> None:
    """Raises a clear error if the code is wrong or expired; deletes it when used."""
    db = get_db()
    email = email.lower()
    doc = await db.otps.find_one({"email": email, "purpose": purpose})
    if not doc or doc["expires_at"] < now():
        raise HTTPException(400, "This code has expired. Ask for a new one.")
    if doc["tries"] >= MAX_TRIES:
        raise HTTPException(429, "Too many wrong tries. Ask for a new code.")
    if not hmac.compare_digest(doc["code_hash"], _hash(email, purpose, code.strip())):
        await db.otps.update_one({"_id": doc["_id"]}, {"$inc": {"tries": 1}})
        left = MAX_TRIES - doc["tries"] - 1
        raise HTTPException(400, f"Wrong code. {left} {'try' if left == 1 else 'tries'} left." if left else "Wrong code. Ask for a new one.")
    await db.otps.delete_one({"_id": doc["_id"]})
