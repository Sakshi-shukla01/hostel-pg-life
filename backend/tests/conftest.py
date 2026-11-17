import os
import tempfile

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

os.environ["GEMINI_API_KEY"] = ""  # tests run in offline AI mode
os.environ["REDIS_URL"] = ""
os.environ["SMTP_USER"] = ""  # tests use dev-mode codes
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["SHOW_DEV_CODES"] = "true"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    db.set_client(AsyncMongoMockClient())
    await db.create_indexes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
