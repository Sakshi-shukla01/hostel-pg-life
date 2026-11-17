import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import create_indexes
from app.routers import ai_tools, auth, chat, complaints, market, matches, profiles, rooms

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_indexes()
    logging.getLogger("app").info("AI mode: %s", "Gemini" if settings.ai_enabled else "offline fallback (no GEMINI_API_KEY)")
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-powered roommate matching and shared-living platform for hostels and PGs.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, profiles, matches, chat, rooms, complaints, market, ai_tools):
    app.include_router(r.router)

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "ai_mode": "gemini" if settings.ai_enabled else "offline"}
