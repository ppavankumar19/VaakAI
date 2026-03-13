import logging
import os

from database import SessionLocal
from models.schemas import Session, TranscriptChunk
from services.audio_extractor import extract_audio
from services.sarvam_client import transcribe_audio
from services.llm_chain import run_analysis
from services.vector_store import embed_chunks

logger = logging.getLogger(__name__)

# Approximate token size in characters (1 token ≈ 4 chars)
CHUNK_CHARS = 4096   # ~1024 tokens
OVERLAP_CHARS = 512  # ~128 tokens


def _update(db, session_id, *, status: str = None, stage: str = None, progress: int = None):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        return
    if status is not None:
        session.status = status
    if stage is not None:
        session.stage = stage
    if progress is not None:
        session.progress_percent = progress
    db.commit()


def _make_text_chunks(transcript_text: str, segments: list) -> list:
    """
    Split transcript into overlapping character-based chunks with timestamp metadata.
    Returns list of {text, start_ms, end_ms, chunk_index}.
    """
    if not transcript_text:
        return []

    chunks = []
    start_char = 0
    chunk_index = 0

    while start_char < len(transcript_text):
        end_char = min(start_char + CHUNK_CHARS, len(transcript_text))
        chunk_text = transcript_text[start_char:end_char]

        # Find time range by scanning segments for overlapping character positions
        chunk_start_ms = 0
        chunk_end_ms = 0
        pos = 0
        for seg in segments:
            seg_end = pos + len(seg["text"]) + 1  # +1 for joining space
            if pos <= start_char < seg_end:
                chunk_start_ms = seg["start_ms"]
            if pos < end_char <= seg_end:
                chunk_end_ms = seg["end_ms"]
                break
            pos = seg_end

        if chunk_end_ms == 0 and segments:
            chunk_end_ms = segments[-1]["end_ms"]

        chunks.append({
            "text": chunk_text,
            "start_ms": chunk_start_ms,
            "end_ms": chunk_end_ms,
            "chunk_index": chunk_index,
        })

        start_char = end_char - OVERLAP_CHARS
        chunk_index += 1

    return chunks


def _save_chunks(db, session_id, chunks: list):
    for chunk in chunks:
        db.add(TranscriptChunk(
            session_id=session_id,
            chunk_index=chunk["chunk_index"],
            start_ms=chunk["start_ms"],
            end_ms=chunk["end_ms"],
            text=chunk["text"],
        ))
    db.commit()


def process_video(session_id: str, video_path: str, language: str, source_url: str = None):
    """
    Full processing pipeline. Called as a FastAPI background task (runs in thread pool).

    Stages and progress:
      extracting_audio  10%
      transcribing      25%
      analyzing         60%
      embedding         85%
      complete         100%
    """
    db = SessionLocal()
    audio_path = os.path.splitext(video_path)[0] + ".wav"

    try:
        # ── 1. Extract audio ────────────────────────────────────────────────
        _update(db, session_id, status="processing", stage="extracting_audio", progress=10)
        extract_audio(video_path, audio_path)

        # ── 2. Transcribe ────────────────────────────────────────────────────
        _update(db, session_id, stage="transcribing", progress=25)
        segments = transcribe_audio(audio_path, language)
        transcript_text = " ".join(s["text"] for s in segments)

        # ── 3. Analyze ───────────────────────────────────────────────────────
        _update(db, session_id, stage="analyzing", progress=60)
        analysis = run_analysis(transcript_text, segments)

        # ── 4. Embed chunks for RAG Q&A ──────────────────────────────────────
        _update(db, session_id, stage="embedding", progress=85)
        chunks = _make_text_chunks(transcript_text, segments)
        _save_chunks(db, session_id, chunks)
        embed_chunks(session_id, chunks)

        # ── 5. Persist final results ─────────────────────────────────────────
        session = db.query(Session).filter(Session.id == session_id).first()
        session.transcript_text = transcript_text
        result: dict = {"transcript": segments, "analysis": analysis}
        if source_url:
            result["source_url"] = source_url
        session.analysis_json = result
        session.status = "complete"
        session.stage = "complete"
        session.progress_percent = 100
        db.commit()

    except Exception as exc:
        logger.error("Pipeline failed for session %s: %s", session_id, exc, exc_info=True)
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.status = "failed"
                session.stage = "failed"
                session.error_message = str(exc)
                db.commit()
        except Exception:
            pass

    finally:
        db.close()
        for path in (video_path, audio_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def process_url(session_id: str, url: str, language: str):
    """Background task: download YouTube video then run the standard pipeline."""
    from services.url_downloader import download_youtube_video, URLDownloadError

    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    db = SessionLocal()
    try:
        _update(db, session_id, status="processing", stage="downloading", progress=3)
        video_path, title = download_youtube_video(url, session_id, upload_dir)

        session = db.query(Session).filter(Session.id == session_id).first()
        if session:
            session.file_name = title
            session.file_size_bytes = os.path.getsize(video_path)
            db.commit()

    except URLDownloadError as e:
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.status = "failed"
                session.stage = "failed"
                session.error_message = str(e)
                db.commit()
        except Exception:
            pass
        db.close()
        return

    except Exception as exc:
        logger.error("URL download failed for %s: %s", session_id, exc, exc_info=True)
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.status = "failed"
                session.stage = "failed"
                session.error_message = str(exc)
                db.commit()
        except Exception:
            pass
        db.close()
        return

    else:
        db.close()

    process_video(session_id, video_path, language, source_url=url)
