"""Quick demo without MongoDB or Docker: in-memory database, auto-seeded.

    pip install -r requirements-dev.txt
    python -m scripts.demo_server

Data is lost when you stop it. For real use, run with MongoDB (see README).
"""
import asyncio

import uvicorn
from mongomock_motor import AsyncMongoMockClient

from app import db

db.set_client(AsyncMongoMockClient())

from app.main import app  # noqa: E402
from scripts import seed  # noqa: E402


async def main():
    await seed.main()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    asyncio.run(main())
