"""Thin client for the Google Gemini API (free tier) using plain HTTPS.

Get a free key at https://aistudio.google.com/apikey and set GEMINI_API_KEY.
Every function raises AIUnavailable when there is no key or the call fails,
so each feature can fall back to its offline version and the app never breaks.
"""
import asyncio
import base64
import json
import logging
import re

import httpx

from app.config import get_settings

log = logging.getLogger("ai")
BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class AIUnavailable(Exception):
    pass


def _headers() -> dict:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AIUnavailable("No GEMINI_API_KEY set")
    return {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}


async def _post(url: str, body: dict) -> dict:
    """Calls Gemini; retries once if Google is busy (429/500/503) or the network fails."""
    headers = _headers()
    last = "unknown error"
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            last = f"{type(exc).__name__}: {exc}"
            log.warning("Gemini network error: %s", last)
        else:
            if resp.status_code == 200:
                return resp.json()
            last = f"Gemini returned {resp.status_code}"
            log.warning("Gemini error %s: %s", resp.status_code, resp.text[:300])
            if resp.status_code not in (429, 500, 503):
                break  # a real error (bad key, wrong model): retrying won't help
        if attempt == 0:
            await asyncio.sleep(2)
    raise AIUnavailable(last)


def _text_of(data: dict) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError) as exc:
        raise AIUnavailable("Empty Gemini response") from exc


def _parse_json(text: str) -> dict | list:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIUnavailable("Model did not return valid JSON") from exc


async def generate(
    messages: list[dict] | str,
    system: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.5,
    image: tuple[bytes, str] | None = None,
):
    """messages: a prompt string, or a list of {"role": "user"|"model", "text": str}."""
    settings = get_settings()
    if isinstance(messages, str):
        messages = [{"role": "user", "text": messages}]
    contents = []
    for i, m in enumerate(messages):
        parts: list[dict] = [{"text": m["text"]}]
        if image and i == len(messages) - 1:
            data, mime = image
            parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}})
        contents.append({"role": m["role"], "parts": parts})
    body: dict = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    data = await _post(f"{BASE}/{settings.gemini_model}:generateContent", body)
    text = _text_of(data)
    return _parse_json(text) if json_mode else text


async def embed(text: str) -> list[float]:
    settings = get_settings()
    body = {
        "model": f"models/{settings.gemini_embed_model}",
        "content": {"parts": [{"text": text[:8000]}]},
        "outputDimensionality": 768,
    }
    data = await _post(f"{BASE}/{settings.gemini_embed_model}:embedContent", body)
    try:
        return data["embedding"]["values"]
    except KeyError as exc:
        raise AIUnavailable("No embedding returned") from exc
