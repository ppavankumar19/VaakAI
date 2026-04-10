# VoiceIQ — Workflow & Process Flow

This document describes every major workflow in the system: user journeys, backend pipelines, data flows, and component interactions.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                             │
│                                                                 │
│  ┌──────────────┐   ┌─────────────────┐   ┌─────────────────┐  │
│  │ Upload Screen │   │ Processing Screen│   │ Results Screen  │  │
│  │  (file/URL)  │──▶│  (live progress) │──▶│ (full dashboard)│  │
│  └──────────────┘   └─────────────────┘   └─────────────────┘  │
└────────────────────────────┬───────────────────────────────────┘
                             │ HTTP / REST
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI BACKEND                            │
│                                                                 │
│  POST /api/upload          GET /api/session/{id}                │
│  POST /api/upload-url      POST /api/analyze/ask                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Background Pipeline                    │   │
│  │  FFmpeg ──▶ Sarvam.ai ──▶ Groq (×5 parallel) ──▶ DB    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬──────────────────┬───────────────────┬────────────────┘
         │                  │                   │
         ▼                  ▼                   ▼
  ┌─────────────┐  ┌─────────────────┐  ┌─────────────┐
  │  PostgreSQL  │  │    ChromaDB     │  │  Local Disk │
  │  (sessions, │  │  (transcript    │  │  (uploads/) │
  │   analysis) │  │   embeddings)   │  │             │
  └─────────────┘  └─────────────────┘  └─────────────┘
```

---

## 2. User Journey

### 2.1 File Upload Flow

```
User                    Frontend                  Backend
 │                         │                         │
 │  Drag & drop or         │                         │
 │  click to browse ──────▶│                         │
 │                         │  Validate (ext, ≤500MB) │
 │                         │  Show file preview      │
 │                         │                         │
 │  Select language        │                         │
 │  Click "Analyze" ──────▶│                         │
 │                         │  XHR multipart POST     │
 │                         │  /api/upload ──────────▶│ 202 Accepted
 │                         │◀── {session_id} ────────│
 │                         │                         │
 │                         │  Poll every 3s          │
 │                         │  GET /api/session/{id} ─│
 │  (See progress bar,     │◀── {status, stage, %} ──│
 │   stage labels)         │         ...             │
 │                         │  (status: "complete")   │
 │                         │◀── {transcript, analysis}│
 │                         │                         │
 │  Results Dashboard ◀────│                         │
```

### 2.2 YouTube URL Flow

```
User                    Frontend                  Backend
 │                         │                         │
 │  Enter YouTube URL      │                         │
 │  Click "Analyze" ──────▶│                         │
 │                         │  Validate URL format    │
 │                         │  POST /api/upload-url ─▶│ 202 Accepted
 │                         │◀── {session_id} ────────│ (yt-dlp spawned)
 │                         │                         │
 │                         │  Poll every 3s          │
 │  (stages: downloading,  │  GET /api/session/{id} ─│
 │   extracting, analyzing)│◀── {status, stage, %} ──│
 │                         │                         │
 │  Results Dashboard ◀────│◀── {transcript, analysis}│
```

### 2.3 RAG Q&A Flow

```
User                    Frontend                  Backend           ChromaDB
 │                         │                         │                  │
 │  (On Results screen)    │                         │                  │
 │  Type question or       │                         │                  │
 │  click suggested chip ─▶│                         │                  │
 │                         │  POST /api/analyze/ask ▶│                  │
 │                         │  {session_id, question} │  vector search ─▶│
 │                         │                         │◀── top-5 chunks ─│
 │                         │                         │  Groq LLM call   │
 │                         │◀── {answer, segments} ──│                  │
 │                         │                         │                  │
 │  See answer + clickable │                         │                  │
 │  timestamp chips ◀──────│                         │                  │
 │  Click chip → seek ─────│                         │                  │
```

---

## 3. Backend Processing Pipeline

### 3.1 Video/Audio File Pipeline

```
POST /api/upload (202 Accepted)
         │
         │  (Immediate return to frontend)
         │
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Background Task (pipeline.py)                   │
│                                                                    │
│  STAGE 1 — Extract Audio          [Progress: 10%]                 │
│  ┌────────────────────────────────────────────────┐               │
│  │  audio_extractor.py                            │               │
│  │  ffmpeg -i input.mp4 -vn -ar 16000 -ac 1 \    │               │
│  │         -f wav output.wav                      │               │
│  │  → 16kHz mono WAV (Sarvam.ai optimal format)  │               │
│  └────────────────────────────────────────────────┘               │
│                    │                                               │
│                    ▼                                               │
│  STAGE 2 — Transcribe              [Progress: 25%]                │
│  ┌────────────────────────────────────────────────┐               │
│  │  sarvam_client.py                              │               │
│  │                                                │               │
│  │  If audio ≤ 25s: send directly                │               │
│  │  If audio > 25s: split into 25s chunks,        │               │
│  │                  transcribe each,              │               │
│  │                  merge with time offsets       │               │
│  │                                                │               │
│  │  POST https://api.sarvam.ai/speech-to-text    │               │
│  │  model: saarika:v2.5                           │               │
│  │  with_timestamps: true                         │               │
│  │  with_disfluency: true  (preserves fillers)   │               │
│  │                                                │               │
│  │  → [{start_ms, end_ms, text, confidence}]     │               │
│  └────────────────────────────────────────────────┘               │
│                    │                                               │
│                    ▼                                               │
│  STAGE 3 — Analyze                 [Progress: 60%]                │
│  ┌────────────────────────────────────────────────┐               │
│  │  llm_chain.py  →  run_analysis()               │               │
│  │                                                │               │
│  │  LOCAL (no API):                               │               │
│  │  • Filler word count (regex, 11 words)         │               │
│  │  • Vocabulary richness (unique/total ratio)    │               │
│  │  • WPM pace (per 60s window)                  │               │
│  │                                                │               │
│  │  PARALLEL (ThreadPoolExecutor, 5 threads):     │               │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────┐ │               │
│  │  │ summary  │ │tech_terms│ │   grammar     │ │               │
│  │  │ (Groq)   │ │ (Groq)   │ │   score (Groq)│ │               │
│  │  └──────────┘ └──────────┘ └───────────────┘ │               │
│  │  ┌──────────┐ ┌──────────┐                    │               │
│  │  │sentiment │ │  topics  │                    │               │
│  │  │ (Groq)   │ │ (Groq)   │                    │               │
│  │  └──────────┘ └──────────┘                    │               │
│  │                                                │               │
│  │  SEQUENTIAL (depends on grammar_score):        │               │
│  │  ┌──────────────────────────────────────┐     │               │
│  │  │ improvement_tips (Groq)              │     │               │
│  │  └──────────────────────────────────────┘     │               │
│  └────────────────────────────────────────────────┘               │
│                    │                                               │
│                    ▼                                               │
│  STAGE 4 — Persist Results        [Progress: 100%]                │
│  ┌────────────────────────────────────────────────┐               │
│  │  PostgreSQL: sessions table                    │               │
│  │  • analysis_json ← full results (JSONB)        │               │
│  │  • transcript_text ← full transcript           │               │
│  │  • status = "complete"  ← frontend unblocks    │               │
│  └────────────────────────────────────────────────┘               │
│                    │                                               │
│                    ▼                                               │
│  STAGE 5 — Embed Transcript (non-blocking)  [Progress: 85%]      │
│  ┌────────────────────────────────────────────────┐               │
│  │  vector_store.py + pipeline._make_text_chunks()│               │
│  │  • Chunk transcript (4096 chars, 512 overlap)  │               │
│  │  • Save chunks to transcript_chunks table      │               │
│  │  • Embed into ChromaDB (all-MiniLM-L6-v2)     │               │
│  │  • Failure here → warning logged, not fatal    │               │
│  └────────────────────────────────────────────────┘               │
│                    │                                               │
│                    ▼                                               │
│  CLEANUP — Delete files from disk                                 │
│  • uploads/{session_id}.mp4  (video)                             │
│  • uploads/{session_id}.wav  (audio)                             │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 YouTube URL Pipeline

```
POST /api/upload-url (202 Accepted)
         │
         ▼
┌─────────────────────────────────────────┐
│  url_downloader.py                      │
│  validate_youtube_url(url)              │
│  → reject if not youtube.com / youtu.be │
│                                         │
│  yt-dlp download:                       │
│  • best mp4 ≤ 720p                      │
│  • max file size: 500 MB                │
│  • max duration: 60 minutes             │
│  → (video_path, title)                  │
└──────────────┬──────────────────────────┘
               │
               ▼
   (same as File Pipeline above)
```

---

## 4. Data Flow Diagram

```
                    ┌───────────────────┐
                    │   User Upload     │
                    │  (file or URL)    │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │     PostgreSQL     │
                    │  sessions table   │
                    │  status:processing│
                    └─────────┬─────────┘
                              │
               ┌──────────────┼──────────────┐
               │              │              │
    ┌──────────▼──────┐       │    ┌─────────▼──────┐
    │   FFmpeg         │       │    │  yt-dlp        │
    │  (audio extract) │       │    │  (URL download) │
    └──────────┬───────┘       │    └─────────┬──────┘
               │               │              │
    ┌──────────▼───────────────┘──────────────┘
    │                                         │
    │              Sarvam.ai                  │
    │          saarika:v2.5 STT               │
    │    [{start_ms, end_ms, text, conf}]     │
    └──────────────────────┬──────────────────┘
                           │
              ┌────────────┼───────────────┐
              │            │               │
   ┌──────────▼──────┐     │    ┌──────────▼──────┐
   │  Local Metrics   │     │    │  Groq (×5+1)    │
   │  • Filler words  │     │    │  summary        │
   │  • Vocab richness│     │    │  tech_terms     │
   │  • WPM pace      │     │    │  grammar        │
   └──────────┬───────┘     │    │  sentiment      │
              │             │    │  topics         │
              └─────────────┘    │  improvement    │
                           │     └──────────┬──────┘
                           │                │
                    ┌──────▼────────────────▼──────┐
                    │         analysis_json         │
                    │  {summary, tech_terms, filler │
                    │   words, pace, grammar, topics│
                    │   sentiment, improvement_tips}│
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │   PostgreSQL  (status:complete)│
                    │   + ChromaDB embeddings        │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │    Frontend Polling (3s)       │
                    │    GET /api/session/{id}       │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │      Results Dashboard        │
                    │  transcript, charts, RAG Q&A  │
                    └───────────────────────────────┘
```

---

## 5. API Endpoints Reference

| Endpoint | Method | Body / Params | Response | Rate Limit |
|----------|--------|---------------|----------|-----------|
| `/health` | GET | — | `{"status":"ok"}` | None |
| `/api/upload` | POST | `file` (multipart), `language` (form) | `{session_id, status, estimated_duration_seconds}` | 5/hour/IP |
| `/api/upload-url` | POST | `{url, language}` (JSON) | `{session_id, status, estimated_duration_seconds}` | 5/hour/IP |
| `/api/session/{id}` | GET | UUID path param | `{status, stage, progress_percent}` or full results | None |
| `/api/analyze/ask` | POST | `{session_id, question}` (JSON) | `{answer, source_segments}` | None |

### Session Status States

```
uploading ──▶ processing ──▶ complete
                  │
                  └──▶ failed
```

### Session Response (complete)

```json
{
  "status": "complete",
  "transcript": [
    {"start_ms": 0, "end_ms": 4200, "text": "Hello everyone...", "confidence": 0.97}
  ],
  "analysis": {
    "summary": "The speaker discusses...",
    "technical_terms": ["FastAPI", "ChromaDB"],
    "project_keywords": ["VoiceIQ", "pipeline"],
    "filler_words": {
      "total_count": 12,
      "percentage": 2.4,
      "breakdown": {"um": 5, "uh": 3, "like": 4}
    },
    "vocabulary_richness": {
      "total_words": 500,
      "unique_words": 312,
      "richness_score": 62.4
    },
    "pace": {
      "avg_wpm": 148,
      "rating": "ideal",
      "timeline": [{"segment": 1, "wpm": 145}]
    },
    "grammar_score": 82,
    "sentiment": {
      "overall": "confident",
      "score": 78,
      "timeline": [{"start": "0:00", "end": "1:00", "tone": "neutral"}]
    },
    "topics": [
      {"topic": "Project Introduction", "start": "0:00"}
    ],
    "improvement_tips": [
      "1. Reduce filler words by pausing instead of saying 'um'."
    ]
  }
}
```

---

## 6. Frontend Screen Flow

```
                 ┌─────────────────┐
    Page Load ──▶│  Upload Screen  │
                 └────────┬────────┘
                          │
          ┌───────────────┴──────────────┐
          │  Tab: File Upload            │  Tab: YouTube URL
          │  ┌─────────────────────┐     │  ┌──────────────────────┐
          │  │  Drop Zone          │     │  │  URL Input           │
          │  │  (drag & drop,      │     │  │  (youtube.com,       │
          │  │   click to browse)  │     │  │   youtu.be)          │
          │  │                     │     │  │                      │
          │  │  Language Selector  │     │  │  Language Selector   │
          │  │  Analyze Button     │     │  │  Analyze Button      │
          │  └─────────────────────┘     │  └──────────────────────┘
          └───────────────┬──────────────┘
                          │ Click Analyze
                          ▼
                 ┌─────────────────┐
                 │Processing Screen│
                 │                 │
                 │  EQ animation   │
                 │  Stage label    │
                 │  Progress bar   │
                 │  (polls every 3s│
                 └────────┬────────┘
                          │  status == "complete"
                          ▼
                 ┌─────────────────────────────────────────┐
                 │             Results Screen              │
                 │                                         │
                 │  ┌──────────────────┬────────────────┐  │
                 │  │  Video / Audio   │   Transcript   │  │
                 │  │     Player       │  (searchable,  │  │
                 │  │                  │   highlighted, │  │
                 │  │                  │   click-seek)  │  │
                 │  └──────────────────┴────────────────┘  │
                 │                                         │
                 │  ┌──────────────────────────────────┐   │
                 │  │     6 Metric Cards               │   │
                 │  │  Words │ Unique │ WPM │ Filler % │   │
                 │  │  Grammar Score  │  Confidence    │   │
                 │  └──────────────────────────────────┘   │
                 │                                         │
                 │  ┌──────────┐ ┌─────────┐ ┌─────────┐  │
                 │  │  Radar   │ │ Filler  │ │  Pace   │  │
                 │  │  Chart   │ │Bar Chart│ │  Chart  │  │
                 │  └──────────┘ └─────────┘ └─────────┘  │
                 │                                         │
                 │  Topics │ Summary │ Tech Terms │ Tips   │
                 │                                         │
                 │  ┌──────────────────────────────────┐   │
                 │  │          RAG Q&A Panel           │   │
                 │  │  Suggested question chips        │   │
                 │  │  Message thread (Q + A pairs)    │   │
                 │  │  Source timestamp chips          │   │
                 │  └──────────────────────────────────┘   │
                 └─────────────────────────────────────────┘
```

---

## 7. Component Interactions Map

```
frontend/app.js
│
├── startUpload() / startUrlUpload()
│     └──▶ POST /api/upload or /api/upload-url
│
├── pollSession()  [every 3s]
│     └──▶ GET /api/session/{id}
│           ├── processing → update progress bar
│           └── complete   → renderResults()
│
├── renderResults()
│     ├── renderTranscript()  →  highlightText() (filler=red, tech=blue)
│     ├── renderMetricCards() →  display 6 KPI values
│     ├── renderCharts()      →  Chart.js (radar, bar, line)
│     ├── renderTopics()      →  clickable topic blocks
│     └── renderAnalysisCards() → summary, tech terms, tips
│
├── setupVideoSync()          →  timeupdate → highlight active segment
├── seekVideo(ms)             →  seek video or YouTube iframe
├── setupTranscriptSearch()   →  filter segments by text
├── exportTxt() / exportPdf() →  download transcript or print
│
└── setupRagPanel()
      └──▶ POST /api/analyze/ask
            └── display answer + clickable timestamp chips


backend/pipeline.py  →  orchestrates all services:
│
├── audio_extractor.py  →  FFmpeg subprocess
├── sarvam_client.py    →  Sarvam.ai REST API  (chunks > 25s audio)
├── llm_chain.py        →  Groq API (5 parallel + 1 sequential)
│     └── prompts/*.txt →  system prompt templates
└── vector_store.py     →  ChromaDB (embed after complete, search for RAG)
```

---

## 8. Database Schema

```
sessions
─────────────────────────────────────────────────────
id                UUID        PK
created_at        TIMESTAMP   auto
file_name         VARCHAR
file_size_bytes   BIGINT
duration_seconds  FLOAT
language_code     VARCHAR     default "en-IN"
status            VARCHAR     uploading|processing|complete|failed
stage             VARCHAR     current pipeline stage label
progress_percent  INTEGER     0–100
sarvam_job_id     VARCHAR     nullable
transcript_text   TEXT        full transcript (plain)
analysis_json     JSONB       complete analysis results
error_message     TEXT        nullable, populated on failure

transcript_chunks
─────────────────────────────────────────────────────
id                INTEGER     PK (autoincrement)
session_id        UUID        FK → sessions.id (cascade delete)
chunk_index       INTEGER
start_ms          INTEGER
end_ms            INTEGER
text              TEXT
embedding_id      VARCHAR     ChromaDB document ID
```

---

## 9. Environment & Infrastructure

### Required Services

| Service | Purpose | Notes |
|---------|---------|-------|
| PostgreSQL | Session & results storage | Must be running before backend start |
| ChromaDB | Vector embeddings for RAG | Auto-initialized on startup, local persistent |
| FFmpeg | Audio extraction from video | Must be on system PATH |
| Sarvam.ai | Speech-to-text transcription | Free tier: `dashboard.sarvam.ai` |
| Groq | LLM inference (analysis) | Free tier: `console.groq.com` |

### Environment Variables

```env
SARVAM_API_KEY=         # Required: Sarvam.ai speech-to-text
GROQ_API_KEY=           # Required: Groq LLM inference
GROQ_MODEL=             # Optional: default llama-3.1-70b-versatile
DATABASE_URL=           # Required: postgresql://user:pass@host/db
CORS_ORIGINS=           # Optional: comma-separated allowed origins
UPLOAD_DIR=./uploads    # Optional: file storage location
CHROMA_PERSIST_DIR=./chroma_data  # Optional: vector DB storage
```

### Startup Sequence

```
1. PostgreSQL must be running
2. cd backend && source venv/bin/activate
3. cp ../.env.example .env  (fill in API keys and DATABASE_URL)
4. pip install -r requirements.txt
5. uvicorn main:app --reload --port 8523
   ├── init_db() creates tables (sessions, transcript_chunks)
   ├── mkdir uploads/ if not exists
   └── mkdir chroma_data/ if not exists
6. Open http://localhost:8523/
```

---

## 10. Error Handling & Recovery

| Failure Point | Behavior | User Impact |
|--------------|----------|-------------|
| Invalid file type / size | Rejected at upload endpoint (400) | Immediate error message |
| FFmpeg not found or fails | Session marked `failed` | Retry button shown |
| Sarvam.ai API error | Session marked `failed` | Retry button shown |
| Groq API error (any call) | Session marked `failed` | Retry button shown |
| ChromaDB embedding fails | Warning logged, session stays `complete` | RAG Q&A unavailable but results visible |
| YouTube video > 60 min | Rejected at download step | Session marked `failed` |
| YouTube video > 500 MB | Rejected by yt-dlp | Session marked `failed` |
| Rate limit exceeded (>5/hr) | 429 Too Many Requests | Frontend shows error |

---

## 11. Supported File Formats

### Video
`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.flv`, `.wmv`, `.m4v`, `.3gp`, `.ogv`

### Audio (direct upload)
`.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.m4a`, `.opus`, `.wma`, `.aiff`

### Online
YouTube links (`youtube.com`, `youtu.be`, `www.youtube.com`, `m.youtube.com`)

---

*Generated from codebase analysis. Last updated: 2026-04-10*
