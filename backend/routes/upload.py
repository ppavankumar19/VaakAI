import os
import uuid
from uuid import UUID as PyUUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models.schemas import Session as SessionModel
from pipeline import process_video

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
MAX_FILE_BYTES = 500 * 1024 * 1024  # 500 MB


@router.post("/upload", status_code=202)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form(default="en-IN"),
    db: DBSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    session_id = str(uuid.uuid4())
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    video_path = os.path.join(UPLOAD_DIR, f"{session_id}{ext}")

    # Stream to disk while enforcing size limit
    total_bytes = 0
    try:
        with open(video_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_BYTES:
                    raise HTTPException(status_code=413, detail="File exceeds 500 MB limit")
                f.write(chunk)
    except HTTPException:
        if os.path.exists(video_path):
            os.remove(video_path)
        raise

    # Create session record
    session = SessionModel(
        id=session_id,
        file_name=file.filename,
        file_size_bytes=total_bytes,
        language_code=language,
        status="processing",
        stage="uploading",
        progress_percent=5,
    )
    db.add(session)
    db.commit()

    # Kick off background processing
    background_tasks.add_task(process_video, session_id, video_path, language)

    # Rough estimate: ~1 second per MB of video
    estimated_seconds = max(30, total_bytes // (1024 * 1024))

    return {
        "session_id": session_id,
        "status": "processing",
        "estimated_duration_seconds": estimated_seconds,
    }


@router.get("/session/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    try:
        uid = PyUUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    session = db.query(SessionModel).filter(SessionModel.id == uid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "failed":
        return {
            "session_id": str(session.id),
            "status": "failed",
            "error": session.error_message or "Processing failed",
        }

    if session.status != "complete":
        return {
            "session_id": str(session.id),
            "status": "processing",
            "stage": session.stage,
            "progress_percent": session.progress_percent,
        }

    data = session.analysis_json or {}
    return {
        "session_id": str(session.id),
        "status": "complete",
        "transcript": data.get("transcript", []),
        "analysis": data.get("analysis", {}),
    }
