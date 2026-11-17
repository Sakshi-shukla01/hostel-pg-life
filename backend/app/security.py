from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import get_db, oid

bearer = HTTPBearer(auto_error=False)

# Email domains that earn a "verified student" badge (simple, explainable rule)
STUDENT_DOMAINS = (".edu", ".ac.in", ".edu.in")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def is_student_email(email: str) -> bool:
    domain = email.lower().split("@")[-1]
    return any(domain.endswith(d) for d in STUDENT_DOMAINS)


def create_token(user_id: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    user_id = decode_token(creds.credentials)
    user = await get_db().users.find_one({"_id": oid(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_warden(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("warden", "admin"):
        raise HTTPException(status_code=403, detail="Warden or PG owner only")
    return user
