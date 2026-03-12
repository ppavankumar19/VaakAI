# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**VoiceIQ** (codename: VaakAI) is an AI-powered student speech analyzer. Users upload video files → audio is extracted via FFmpeg → transcribed via Sarvam.ai STT → analyzed by an LLM via a RAG pipeline → results rendered in an interactive dashboard.

Built stack (MVP complete):
- **Backend:** Python + FastAPI, SQLAlchemy, ChromaDB, PostgreSQL
- **Frontend:** HTML5 + CSS3 + Vanilla JS, Chart.js (no build step)
- **APIs:** Sarvam.ai `saarika:v2` (STT, free tier), Groq `llama-3.1-70b-versatile` (LLM, free tier)
- **Infrastructure:** FFmpeg (audio extraction), local filesystem (file storage in MVP)

## Development Setup

### Prerequisites
- Python 3.10+, FFmpeg on PATH, PostgreSQL running
- Sarvam.ai API key (free: dashboard.sarvam.ai)
- Groq API key (free: console.groq.com)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in API keys
uvicorn main:app --reload --port 8000
```

### Frontend
No build step — open `frontend/index.html` directly in Chrome, or it is auto-served at `http://localhost:8000/` when the backend is running.

### Environment Variables
```
SARVAM_API_KEY=        # sarvam.ai free tier
GROQ_API_KEY=          # groq.com free tier
GROQ_MODEL=llama-3.1-70b-versatile   # or llama3-70b-8192, mixtral-8x7b-32768
DATABASE_URL=postgresql://user:pass@localhost/voiceiq
```

## Architecture

### Request Flow
1. `POST /api/upload` — stores video, extracts audio via FFmpeg (`ffmpeg -i input.mp4 -vn -ar 16000 -ac 1 -f wav output.wav`)
2. `sarvam_client.py` — sends WAV to Sarvam.ai (`model: saarika:v2`, `with_disfluency: true` to preserve filler words)
3. `vector_store.py` — chunks transcript (1024 tokens, 128 overlap) and stores in ChromaDB with `session_id`/timestamp metadata
4. `llm_chain.py` — computes local metrics (WPM, filler words, vocab richness) then runs 3 parallel Groq calls: summary, tech terms, improvement tips
5. Results stored as `analysis_json` (JSONB) in PostgreSQL `sessions` table
6. Frontend polls `GET /api/session/{id}` until `status: complete`

### Key Backend Files
```
backend/
├── main.py                      # FastAPI app, CORS, startup, static serving
├── database.py                  # SQLAlchemy engine, Base, get_db, init_db
├── pipeline.py                  # Background job orchestrator
├── routes/upload.py             # POST /api/upload · GET /api/session/{id}
├── routes/analyze.py            # POST /api/analyze/ask (RAG Q&A)
├── services/audio_extractor.py  # FFmpeg subprocess wrapper
├── services/sarvam_client.py    # Sarvam.ai STT → segment list
├── services/llm_chain.py        # Groq calls (_call_llm) + local metric computation
├── services/vector_store.py     # ChromaDB embed_chunks + search
├── models/schemas.py            # ORM: Session, TranscriptChunk
└── prompts/                     # summary, tech_terms, filler_words, improvement_tips
```

### Database
Two tables: `sessions` (UUID PK, status enum, `transcript_text TEXT`, `analysis_json JSONB`) and `transcript_chunks` (FK to sessions, `start_ms`/`end_ms`, `embedding_id` for ChromaDB/Pinecone ref).

### RAG Q&A
`POST /api/analyze/ask` — takes `session_id` + `question`, retrieves relevant chunks from ChromaDB, returns answer with `source_segments` (timestamps for click-to-seek).

## MVP Scope (Phase 1)

P0 features: video upload, FFmpeg audio extraction, Sarvam.ai transcription, LLM analysis (summary + tech terms + filler words + improvement tips), transcript display, basic results panel.

P1 features: synchronized video+transcript player (click-to-seek), vocabulary richness score, WPM pace analysis, Chart.js dashboard, PDF/TXT export.

P2+ features (not MVP): RAG Q&A, grammar score, sentiment analysis, topic segmentation, multi-language UI.

No user authentication in MVP — sessions are anonymous UUIDs.

## Key Technical Decisions

- **Sarvam.ai** for STT (free tier, Indian English/languages); fallback to Whisper if needed
- **Groq** for LLM inference (free tier) — model configurable via `GROQ_MODEL` env var; default `llama-3.1-70b-versatile`
- **ChromaDB locally, Pinecone in production** for vector storage
- **Embedding model:** ChromaDB default (`all-MiniLM-L6-v2`, managed by chroma)
- Videos over 60 minutes chunked into 25-minute segments before STT
- Max file size: 500MB; rate limit: 5 uploads/IP/hour
- Uploaded videos deleted after 24 hours

---

## Engineering Behavior

### Role
You are the hands; the human is the architect. Move fast, but never faster than the human can verify.

### Before implementing anything non-trivial, surface assumptions explicitly:
```
ASSUMPTIONS I'M MAKING:
1. [assumption]
2. [assumption]
→ Correct me now or I'll proceed with these.
```
Never silently fill in ambiguous requirements.

### When confused by inconsistencies or conflicting requirements:
1. STOP — do not guess.
2. Name the specific confusion.
3. Present the tradeoff or ask the clarifying question.
4. Wait for resolution before continuing.

### For multi-step tasks, emit a plan before executing:
```
PLAN:
1. [step] — [why]
2. [step] — [why]
→ Executing unless you redirect.
```

### After any modification, summarize:
```
CHANGES MADE:
- [file]: [what changed and why]

THINGS I DIDN'T TOUCH:
- [file]: [intentionally left alone because...]

POTENTIAL CONCERNS:
- [any risks or things to verify]
```

### Simplicity enforcement
Before finishing any implementation, ask: can this be done in fewer lines? Are these abstractions earning their complexity? Prefer the boring, obvious solution. If you build 1000 lines and 100 would suffice, you have failed.

### Scope discipline
Touch only what you're asked to touch. Do not remove comments you don't understand, "clean up" code orthogonal to the task, refactor adjacent systems as side effects, or delete seemingly unused code without explicit approval.

### Dead code hygiene
After refactoring, identify now-unreachable code, list it explicitly, and ask before removing it.

### Push back when warranted
When the human's approach has clear problems: point out the issue directly, explain the concrete downside, propose an alternative, then accept their decision if they override. Sycophancy is a failure mode.

### For algorithmic work
1. First implement the obviously-correct naive version and verify correctness.
2. Then optimize while preserving behavior.

### Commit messages
Do NOT add a "Co-Authored-By: Claude" line to commit messages.
