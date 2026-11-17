"""Caching and AI rate limiting. Uses Redis when REDIS_URL is set, else memory."""
import json
import time
from datetime import date

from app.config import get_settings

_memory: dict[str, tuple[float, str]] = {}
_redis = None


def _client():
    global _redis
    url = get_settings().redis_url
    if not url:
        return None
    if _redis is None:
        import redis.asyncio as redis

        _redis = redis.from_url(url, decode_responses=True)
    return _redis


async def cache_get(key: str):
    r = _client()
    try:
        raw = await r.get(key) if r else None
    except Exception:
        raw = None
    if raw is None and key in _memory:
        expires, raw = _memory[key]
        if expires < time.time():
            _memory.pop(key, None)
            raw = None
    return json.loads(raw) if raw else None


async def cache_set(key: str, value, ttl: int = 7 * 24 * 3600) -> None:
    raw = json.dumps(value)
    r = _client()
    try:
        if r:
            await r.set(key, raw, ex=ttl)
            return
    except Exception:
        pass
    _memory[key] = (time.time() + ttl, raw)


async def allow_ai_call(user_id: str) -> bool:
    """Max N AI calls per user per day; over the limit we use the offline fallback."""
    limit = get_settings().ai_daily_limit_per_user
    key = f"ai-count:{user_id}:{date.today().isoformat()}"
    r = _client()
    try:
        if r:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 86400)
            return count <= limit
    except Exception:
        pass
    expires, raw = _memory.get(key, (time.time() + 86400, "0"))
    count = int(raw) + 1
    _memory[key] = (expires, str(count))
    return count <= limit
