from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models.schemas import Session as SessionModel
from services.vector_store import search
from services.llm_chain import _call_llm

router = APIRouter()


class AskRequest(BaseModel):
    session_id: str
    question: str


@router.post("/analyze/ask")
def ask_question(req: AskRequest, db: DBSession = Depends(get_db)):
    try:
        uid = PyUUID(req.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    session = db.query(SessionModel).filter(SessionModel.id == uid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "complete":
        raise HTTPException(status_code=400, detail="Session is not yet complete")

    source_segments = search(req.session_id, req.question, n_results=5)

    if not source_segments:
        return {
            "answer": "I couldn't find relevant sections in the transcript to answer that question.",
            "source_segments": [],
        }

    context = "\n\n".join(s["text"] for s in source_segments)
    prompt = (
        f"Based on the following transcript excerpt:\n\n{context}\n\n"
        f"Answer this question concisely: {req.question}\n\n"
        "If the excerpt doesn't contain enough information, say so clearly."
    )

    answer = _call_llm(prompt, max_tokens=512)

    return {
        "answer": answer.strip(),
        "source_segments": source_segments,
    }
