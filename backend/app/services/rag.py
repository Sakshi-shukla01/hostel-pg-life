"""RAG over a hostel/PG rulebook: chunk -> embed -> retrieve -> grounded answer."""
import io
import re

from app.ai import features, llm
from app.ai.llm import AIUnavailable
from app.db import get_db
from app.services.matching import cosine


def read_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def chunk(text: str, size: int = 600, overlap: int = 100) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=\d+[.)] )", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 1 <= size:
            cur = f"{cur}\n{p}".strip()
        else:
            if cur:
                chunks.append(cur)
            while len(p) > size:
                chunks.append(p[:size])
                p = p[size - overlap:]
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


async def ingest(hostel: str, doc_name: str, text: str, user_id: str) -> int:
    db = get_db()
    await db.rule_chunks.delete_many({"hostel": hostel, "doc_name": doc_name})
    parts = chunk(text)
    for i, part in enumerate(parts):
        embs = await features.embeddings_for(part, user_id)
        await db.rule_chunks.insert_one({"hostel": hostel, "doc_name": doc_name, "index": i, "text": part, **embs})
    return len(parts)


async def retrieve(hostel: str, question: str, user_id: str, k: int = 3) -> list[dict]:
    q = await features.embeddings_for(question, user_id)
    scored = []
    async for c in get_db().rule_chunks.find({"hostel": hostel}):
        u, v, _ = features.best_pair(q, c)
        scored.append((cosine(u, v) or 0.0, c))
    scored.sort(key=lambda x: -x[0])
    return [{"text": c["text"], "doc_name": c["doc_name"], "index": c["index"], "score": round(s, 3)} for s, c in scored[:k] if s > 0]


async def answer(hostel: str, question: str, user_id: str) -> dict:
    hits = await retrieve(hostel, question, user_id)
    if not hits:
        return {"answer": "I couldn't find this in your hostel's rulebook. Please ask the warden.", "sources": [], "source": "offline"}
    context = "\n---\n".join(f"[{i + 1}] {h['text']}" for i, h in enumerate(hits))
    if await features._can_use_ai(user_id):
        try:
            text = await llm.generate(
                "Answer the student's question using ONLY the hostel rulebook excerpts below. If the answer is not "
                "there, say you don't know and suggest asking the warden. Cite excerpts like [1]. Keep it short.\n\n"
                f"Excerpts:\n{context}\n\nQuestion: {question}",
                temperature=0.2,
            )
            return {"answer": text, "sources": hits, "source": "gemini"}
        except AIUnavailable:
            pass
    # Offline: return the best-matching sentences from the top excerpt.
    qwords = set(features.fallback.tokens(question))
    sentences = re.split(r"(?<=[.!?])\s+|\n", hits[0]["text"])
    best = sorted(sentences, key=lambda s: -len(qwords & set(features.fallback.tokens(s))))[:2]
    return {"answer": "From the rulebook [1]: " + " ".join(s.strip() for s in best if s.strip()), "sources": hits, "source": "offline"}
