# VoiceIQ — AI Student Speech Analyzer

> Upload a video or audio recording. Get richer feedback than any interviewer could give in real-time.

---

## What Is VoiceIQ?

**VoiceIQ** (codename: VaakAI) is an AI-powered web application that helps students and candidates improve their spoken communication by analyzing recordings of interviews, presentations, and project demos.

Three input modes → one unified analysis pipeline → rich, actionable dashboard.

---

## Key Features

### Input Modes
- **Video upload** — `.mp4`, `.webm`, `.mov`, `.avi`, `.mkv` (drag-and-drop or click)
- **Audio upload** — `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, `.flac` (no video needed)
- **YouTube URL** — paste any public YouTube link (max 60 min / 500 MB, auto-downloaded)

### Transcription (Sarvam.ai `saarika:v2.5`)
- Full verbatim, timestamped transcript
- Language: auto-detected by default; manually select Indian English, Hindi, Telugu, Tamil, Kannada, or Marathi
- Filler words highlighted in red · technical terms highlighted in blue
- Click any transcript line → video/audio seeks to that moment
- Search bar to find any word or phrase

### AI Analysis (Groq — Llama 3.1 70B)

| Metric | What It Shows |
|---|---|
| Executive Summary | 4–6 sentence summary of spoken content |
| Technical Vocabulary | Domain/tech terms extracted and tagged |
| Filler Word Detection | Count + % of "um", "uh", "basically", "so", etc. |
| Vocabulary Richness | Unique-word ratio vs total words (0–1 score) |
| Pace Analysis | Words per minute — too slow / ideal / too fast |
| Grammar Score | 0–100 grade on grammatical quality |
| Confidence & Tone | Overall confidence score + tone label (confident, hesitant, nervous…) |
| Topic Segmentation | 3–6 auto-detected topic sections with timestamps — click to jump |
| Improvement Tips | Personalized, numbered action items based on all metrics |

### Visual Dashboard (Chart.js)
- **Communication Radar** — 6-axis: Vocabulary · Pace · Grammar · Confidence · Tech Depth · Clarity
- **Filler Word Bar Chart** — frequency breakdown by word
- **Speech Pace Timeline** — WPM per 60-second segment

### RAG Q&A
- Chat-style panel powered by ChromaDB + Groq
- Ask any question about the recording (e.g. "What project was discussed?", "Did I explain clearly?")
- Answers include **source timestamp chips** — click to seek to the exact moment
- 5 suggested quick-question chips pre-loaded

### Export
- Download transcript as `.txt`
- Print / save full analysis as PDF via browser print

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5 + CSS3 + Vanilla JS, Chart.js |
| Backend | Python 3.10+, FastAPI, SQLAlchemy |
| STT | Sarvam.ai `saarika:v2.5` (free tier) |
| LLM | Groq API — `llama-3.1-70b-versatile` (free tier) |
| Vector DB | ChromaDB (local persistent) |
| Audio extraction | FFmpeg |
| YouTube download | yt-dlp |
| Database | PostgreSQL |

---

## Project Structure

```
VaakAI/
├── backend/
│   ├── main.py                    # FastAPI app, CORS, startup, static serving
│   ├── database.py                # SQLAlchemy engine + session factory
│   ├── pipeline.py                # Background processing orchestrator
│   ├── limiter.py                 # Shared slowapi rate limiter instance
│   ├── models/
│   │   └── schemas.py             # ORM models: Session, TranscriptChunk
│   ├── routes/
│   │   ├── upload.py              # POST /api/upload (file & audio)
│   │   │                          # POST /api/upload-url (YouTube)
│   │   │                          # GET  /api/session/{id} (status + results)
│   │   └── analyze.py             # POST /api/analyze/ask (RAG Q&A)
│   ├── services/
│   │   ├── audio_extractor.py     # FFmpeg: extract/convert to 16kHz mono WAV
│   │   ├── sarvam_client.py       # Sarvam.ai STT — chunked transcription
│   │   ├── llm_chain.py           # Groq LLM + local metrics (5 parallel calls)
│   │   ├── url_downloader.py      # YouTube URL validator + yt-dlp downloader
│   │   └── vector_store.py        # ChromaDB embed + similarity search
│   ├── prompts/
│   │   ├── summary_prompt.txt
│   │   ├── tech_terms_prompt.txt
│   │   ├── filler_words_prompt.txt  # (reference only — filler words computed locally)
│   │   ├── grammar_prompt.txt
│   │   ├── sentiment_prompt.txt
│   │   ├── topics_prompt.txt
│   │   └── improvement_tips_prompt.txt
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # All UI: upload · processing · results screens (CSS inlined)
│   └── app.js                     # All frontend logic: upload, polling, rendering, RAG, export
├── CLAUDE.md
├── SCOPE.md
├── SPEC.md
└── .env.example
```

---

## Full Request Flow

```
╔══════════════════════════════════════════════════════════════╗
║  INPUT                                                       ║
║  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  ║
║  │ Video / Audio│  │  Audio file  │  │   YouTube URL     │  ║
║  │ file upload  │  │ .mp3/.wav/…  │  │ (paste & submit)  │  ║
║  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘  ║
╚═════════╪═════════════════╪═══════════════════╪════════════╝
          │                 │                   │
          ▼                 ▼                   ▼
   POST /api/upload   POST /api/upload   POST /api/upload-url
   (multipart form)  (multipart form)    (JSON body)
          │                 │                   │
          └────────────┬────┘                   │ yt-dlp downloads
                       │                        │ video to disk
                       ◄────────────────────────┘
                       │
         [Session created in PostgreSQL — status: processing]
         [Background task started — returns 202 immediately]
                       │
          ┌────────────▼────────────────────────────────┐
          │          PIPELINE (background)              │
          │                                             │
          │  1. FFmpeg: extract/convert → 16kHz WAV     │  10%
          │     (video: strips video stream             │
          │      audio: resamples to 16kHz mono)        │
          │                                             │
          │  2. Sarvam.ai saarika:v2.5 STT              │  25%
          │     • Splits into 25s chunks if > 25s       │
          │     • Sends each chunk, merges timestamps   │
          │     • Returns: [{start_ms, end_ms, text}]   │
          │     • Language: auto-detected unless set    │
          │                                             │
          │  3. Local metrics (no API calls)            │  60%
          │     • WPM + 60s pace timeline               │
          │     • Filler word counts (regex)            │
          │     • Vocabulary richness (unique/total)    │
          │                                             │
          │  4. Groq LLM — 5 parallel calls             │  60%
          │     • summary       (512 tok)               │
          │     • tech_terms    (512 tok) → JSON array  │
          │     • grammar       (64 tok)  → {score: N}  │
          │     • sentiment     (512 tok) → {overall,   │
          │                                score, time} │
          │     • topics        (512 tok) → JSON array  │
          │                                             │
          │  5. Groq LLM — sequential call              │  60%
          │     • improvement_tips (1024 tok)           │
          │       (uses grammar_score from step 4)      │
          │                                             │
          │  6. Save to PostgreSQL                      │  100%
          │     session.analysis_json = {               │
          │       transcript: [...segments],            │
          │       analysis: { summary, technical_terms, │
          │         filler_words, vocabulary_richness,  │
          │         pace, grammar_score, sentiment,     │
          │         topics, improvement_tips }          │
          │     }                                       │
          │     session.status = "complete"             │
          │     ← frontend unblocks here                │
          │                                             │
          │  7. ChromaDB embedding (non-blocking)       │  85%
          │     • Chunks transcript (1024-char, 128     │
          │       overlap), embeds via all-MiniLM-L6-v2 │
          │     • Failure here does NOT affect results  │
          └─────────────────────────────────────────────┘
                       │
                       │  Frontend polls every 3s:
                       │  GET /api/session/{id}
                       │  → {status, stage, progress_percent}
                       │  → once complete: {transcript, analysis}
                       ▼
          ┌────────────────────────────────────────────┐
          │          FRONTEND RENDERS                  │
          │                                            │
          │  • Video player (video files)              │
          │  • Audio player (audio files, compact UI)  │
          │  • YouTube iframe (YouTube uploads)        │
          │  • Timestamped transcript with             │
          │    filler/tech-term highlighting           │
          │  • 6 metric cards                          │
          │  • Radar + Filler bar + Pace timeline      │
          │  • Topic blocks (click-to-seek)            │
          │  • Summary / Tech Terms / Tips cards       │
          │  • RAG Q&A panel                           │
          └────────────────────────────────────────────┘
                       │
          User asks a question:
          POST /api/analyze/ask {session_id, question}
          → ChromaDB top-5 chunks retrieved
          → Groq answers with context
          → {answer, source_segments: [{start_ms, end_ms, text}]}
          → Click timestamp chip → seeks to that moment
```

### API Contract

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/api/upload` | POST | `file` (multipart), `language` (form) | `{session_id, status, estimated_duration_seconds}` |
| `/api/upload-url` | POST | `{url, language}` JSON | `{session_id, status, estimated_duration_seconds}` |
| `/api/session/{id}` | GET | — | Processing: `{status, stage, progress_percent}` · Complete: `{status, transcript, analysis, source_url}` · Failed: `{status, error}` |
| `/api/analyze/ask` | POST | `{session_id, question}` JSON | `{answer, source_segments}` |
| `/health` | GET | — | `{status: "ok"}` |

**Rate limits:** 5 uploads per IP per hour (both `/api/upload` and `/api/upload-url`)

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- FFmpeg installed and on PATH
- PostgreSQL running locally
- [Sarvam.ai](https://dashboard.sarvam.ai) API key (free tier)
- [Groq](https://console.groq.com) API key (free tier)

### 1. Create the PostgreSQL Database

```bash
psql -U postgres -h localhost -c "CREATE DATABASE voiceiq;"
```

> On Windows if `psql` is not on PATH:
> `& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -c "CREATE DATABASE voiceiq;"`

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `backend/.env` and fill in your credentials:

```env
SARVAM_API_KEY=your_sarvam_key_here
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-70b-versatile
DATABASE_URL=postgresql://postgres:your_password@localhost/voiceiq
CORS_ORIGINS=http://localhost:8523,http://127.0.0.1:8523
UPLOAD_DIR=./uploads
CHROMA_PERSIST_DIR=./chroma_data
```

Start the server:

```bash
uvicorn main:app --reload --port 8523
```

### 3. Frontend

No build step. The frontend is automatically served at `http://localhost:8523/` once the backend is running.

---

## Common Issues

| Problem | Likely Cause | Fix |
|---|---|---|
| `FFmpeg audio extraction failed` | FFmpeg not on PATH | Install FFmpeg, add to PATH, restart terminal |
| `SARVAM_API_KEY not set` | Missing `.env` | Copy `.env.example` → `backend/.env`, fill in key |
| Transcript is empty | Audio too quiet or unsupported format | Try converting to WAV first: `ffmpeg -i input.mp3 output.wav` |
| Grammar / sentiment shows `—` | LLM returned unparseable JSON | Transient; retry the upload |
| RAG Q&A: "couldn't find relevant sections" | ChromaDB embedding not yet complete | Wait 10–15s after analysis completes |
| `429 Too Many Requests` | Rate limit hit (5/hour) | Wait 1 hour or change IP |

---

## Who Is This For?

- **Students** preparing for campus placements or internship interviews
- **Job seekers** practicing mock interviews
- **Faculty / Trainers** reviewing student presentation quality
- **Colleges & Bootcamps** wanting automated spoken communication assessment

---

## Roadmap

- [x] v1.0 — Upload + Transcription + AI Analysis + Dashboard
- [x] v1.0.1 — YouTube URL input (paste URL → auto-download + analyze)
- [x] v1.1 — Grammar score + Sentiment/confidence analysis + Topic segmentation
- [x] v1.2 — RAG Q&A panel (ask questions, source timestamp seek)
- [x] v1.2.1 — Bug fixes: sentiment/topics prompt escaping, language auto-detect
- [x] v1.3 — Audio file upload support (MP3, WAV, M4A, AAC, OGG, FLAC)
- [ ] v1.4 — Multi-speaker diarization
- [ ] v1.5 — Comparison mode (two sessions side-by-side)
- [ ] v2.0 — Real-time recording mode (no file upload needed)
- [ ] v2.1 — Student profile + session history
- [ ] v2.2 — Coach/Trainer dashboard for batch review

---

## License

MIT License — Free for personal and educational use.

---

## Credits

- [Sarvam.ai](https://sarvam.ai) — Indian language speech-to-text
- [Groq](https://groq.com) — Fast LLM inference (Llama 3.1)
- [FFmpeg](https://ffmpeg.org) — Audio extraction and conversion
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube video download
- [ChromaDB](https://trychroma.com) — Vector store for RAG
