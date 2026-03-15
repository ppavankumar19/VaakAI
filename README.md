# VoiceIQ — Student Video Speech Analyzer

> Upload a video. Understand what was said. Get smarter feedback than any interviewer could give in real-time.

---

## What Is VoiceIQ?

**VoiceIQ** is an AI-powered web application that helps students and candidates improve their spoken communication by analyzing video recordings of interviews, presentations, and project demos.

Upload a video → audio is extracted via FFmpeg → transcribed by Sarvam.ai → analyzed by Groq LLM → you get a rich, actionable report.

---

## Key Features

### Video Upload & Processing
- Accepts `.mp4`, `.webm`, `.mov`, `.avi`, `.mkv`
- Drag-and-drop or click-to-browse upload
- **Paste a YouTube URL** — public videos downloaded automatically (max 60 min / 500 MB)
- Extracts audio track via FFmpeg server-side

### Speech Transcription (Sarvam.ai)
- Full verbatim timestamped transcript
- Language auto-detected by default; manually select Indian English, Hindi, Telugu, Tamil, Kannada, or Marathi
- Click any transcript line → video seeks to that moment
- Filler words highlighted in red, technical terms in blue
- Search bar to find any word in the transcript

### AI Analysis (Groq — Llama 3.1 70B)

| Analysis | What It Shows |
|---|---|
| Executive Summary | 4–6 sentence summary of spoken content |
| Technical Vocabulary | Domain/tech terms detected and tagged |
| Filler Word Detection | Count and % of "um", "uh", "basically", etc. |
| Vocabulary Richness Score | Unique word ratio vs total words |
| Pace Analysis | Words per minute — too fast, too slow, or ideal |
| Grammar Score | 0–100 grade on grammatical quality of speech |
| Confidence & Tone | Overall confidence score + tone label (confident, hesitant, nervous, etc.) |
| Topic Segmentation | Auto-detected topic sections with timestamps — click to jump |
| Improvement Tips | Personalized, numbered action items based on all metrics |

### Visual Dashboard (Chart.js)
- **Communication Radar** — 6-axis chart: Vocabulary, Pace, Grammar, Confidence, Tech Depth, Clarity (all axes now use real computed data)
- **Filler Word Bar Chart** — frequency breakdown by word
- **Speech Pace Timeline** — WPM per 60-second segment

### Topic Segments Panel
- AI detects 3–6 main topics in the speech
- Displayed as a clickable visual timeline — click any block to jump to that moment in the video

### RAG Q&A — Ask About This Video
- Chat-style panel at the bottom of the results page
- Ask any question about the video content (e.g. "What project was discussed?", "Did I explain clearly?")
- Answer returned with **source timestamp chips** — click to seek the video to the exact moment
- 5 suggested quick-question chips pre-loaded

### Export
- Download transcript as `.txt`
- Print/save full report as PDF via browser print

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5 + CSS3 + Vanilla JS, Chart.js |
| Backend | Python 3.10+, FastAPI, SQLAlchemy |
| STT | Sarvam.ai `saarika:v2.5` (free tier) |
| LLM | Groq API — `llama-3.1-70b-versatile` (free tier) |
| Vector DB | ChromaDB (local persistent) |
| Audio | FFmpeg |
| YouTube Download | yt-dlp |
| Database | PostgreSQL |

---

## Project Structure

```
VaakAI/
├── backend/
│   ├── main.py                    # FastAPI app, CORS, startup
│   ├── database.py                # SQLAlchemy engine + session
│   ├── pipeline.py                # Background processing orchestrator
│   ├── models/
│   │   └── schemas.py             # ORM models: Session, TranscriptChunk
│   ├── routes/
│   │   ├── upload.py              # POST /api/upload, POST /api/upload-url, GET /api/session/{id}
│   │   └── analyze.py             # POST /api/analyze/ask (RAG Q&A)
│   ├── services/
│   │   ├── audio_extractor.py     # FFmpeg wrapper
│   │   ├── sarvam_client.py       # Sarvam.ai STT client
│   │   ├── llm_chain.py           # Groq LLM analysis + local metrics (6 parallel calls)
│   │   ├── url_downloader.py      # YouTube URL validator + yt-dlp downloader
│   │   └── vector_store.py        # ChromaDB embed + search
│   ├── prompts/
│   │   ├── summary_prompt.txt
│   │   ├── tech_terms_prompt.txt
│   │   ├── filler_words_prompt.txt
│   │   ├── grammar_prompt.txt
│   │   ├── sentiment_prompt.txt
│   │   ├── topics_prompt.txt
│   │   └── improvement_tips_prompt.txt
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # All UI: upload, processing, results screens
│   ├── style.css                  # (unused — styles are inlined in index.html)
│   └── app.js                     # All frontend logic
├── CLAUDE.md
├── SCOPE.md
├── SPEC.md
└── .env.example
```

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

> On Windows, if `psql` is not on PATH, use the full path:
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

## How It Works

```
[User Uploads File]               [User Pastes YouTube URL]
        ↓                                  ↓
[POST /api/upload]           [POST /api/upload-url → yt-dlp downloads video]
        ↓                                  ↓
        └──────────────┬───────────────────┘
                       ↓
[FFmpeg extracts 16kHz mono WAV]
        ↓
[Sarvam.ai saarika:v2 → timestamped transcript]
        ↓
[Local metrics: WPM, filler words, vocab richness]
        ↓
[5 parallel Groq calls: summary + tech terms + grammar + sentiment + topics]
        ↓
[Sequential Groq call: improvement tips (uses grammar score from above)]
        ↓
[Transcript chunks embedded → ChromaDB (for RAG Q&A)]
        ↓
[Results saved to PostgreSQL sessions table]
        ↓
[Frontend polls GET /api/session/{id} → renders full dashboard]
```

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
- [x] v1.1 — Grammar score + Sentiment/confidence analysis + Topic segmentation timeline
- [x] v1.2 — RAG Q&A panel (ask questions about the video, source timestamp seek)
- [x] v1.2.1 — Bug fixes: sentiment/topics prompt escaping, auto-detect language default
- [ ] v1.3 — Multi-speaker diarization
- [ ] v1.4 — Comparison mode (two sessions side-by-side)
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
- [FFmpeg](https://ffmpeg.org) — Audio extraction
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube video download
- [ChromaDB](https://trychroma.com) — Vector store
