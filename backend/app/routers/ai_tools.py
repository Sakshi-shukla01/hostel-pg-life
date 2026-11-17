"""AI assistant (agent), hostel rules bot (RAG) and the learning matcher."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import get_db
from app.security import get_current_user, require_warden
from app.services import agent, learner, rag
from app.services.match_query import active_weights

router = APIRouter(tags=["ai"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    history: list[dict] = Field(default_factory=list, max_length=20)


@router.post("/assistant")
async def assistant(body: AskIn, user: dict = Depends(get_current_user)):
    return await agent.ask(body.question, user, body.history)


@router.post("/rules/upload")
async def upload_rules(
    text: str = Form(""),
    file: UploadFile | None = File(None),
    warden: dict = Depends(require_warden),
):
    """Warden uploads the hostel/PG rulebook (PDF or .txt, or pasted text)."""
    name = "rulebook"
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(400, "File must be under 10 MB")
        name = file.filename
        text = rag.read_pdf(data) if file.filename.lower().endswith(".pdf") else data.decode("utf-8", "ignore")
    if len(text.strip()) < 30:
        raise HTTPException(400, "Rulebook text is too short")
    count = await rag.ingest(warden.get("hostel", "default"), name, text, str(warden["_id"]))
    return {"chunks": count, "doc_name": name}


@router.get("/rules/docs")
async def rule_docs(user: dict = Depends(get_current_user)):
    names = await get_db().rule_chunks.distinct("doc_name", {"hostel": user.get("hostel", "default")})
    return {"docs": names}


class RuleQ(BaseModel):
    question: str = Field(min_length=2, max_length=300)


@router.post("/rules/ask")
async def ask_rules(body: RuleQ, user: dict = Depends(get_current_user)):
    return await rag.answer(user.get("hostel", "default"), body.question, str(user["_id"]))


@router.post("/ml/train")
async def train(warden: dict = Depends(require_warden)):
    return await learner.train()


@router.get("/ml/status")
async def ml_status(user: dict = Depends(get_current_user)):
    weights, source = await active_weights()
    latest = await get_db().ml_models.find_one({}, sort=[("trained_at", -1)])
    return {
        "weights_source": source,
        "weights": weights,
        "ratings": await get_db().ratings.count_documents({}),
        "latest_model": {k: latest[k] for k in ("n_ratings", "learned_auc", "default_auc", "active", "trained_at")} if latest else None,
        "ai_mode": "gemini" if get_settings().ai_enabled else "offline",
    }
