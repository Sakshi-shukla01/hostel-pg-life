import os
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile

from app.config import get_settings

ALLOWED_IMAGES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_UPLOAD = 5 * 1024 * 1024


def now() -> datetime:
    """Naive UTC datetime (what MongoDB stores and returns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def save_image(file: UploadFile | None) -> tuple[str | None, tuple[bytes, str] | None]:
    """Saves an uploaded image; returns (public url, (bytes, mime)) for the AI."""
    if file is None or not file.filename:
        return None, None
    if file.content_type not in ALLOWED_IMAGES:
        raise HTTPException(400, "Only JPG, PNG or WEBP images are allowed")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(400, "Image must be under 5 MB")
    folder = get_settings().upload_dir
    os.makedirs(folder, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ALLOWED_IMAGES[file.content_type]}"
    with open(os.path.join(folder, name), "wb") as f:
        f.write(data)
    return f"/uploads/{name}", (data, file.content_type)
