# SPEC.md — VoiceIQ Technical Specification

**Document Version:** 1.1
**Status:** Active Development
**Last Updated:** March 2026

---

## 1. System Overview

VoiceIQ is a full-stack web application that accepts video file uploads, performs speech-to-text transcription using the Sarvam.ai API, and then runs the transcript through a RAG-augmented LLM pipeline to produce a structured analysis report. The frontend provides an interactive experience — synchronized transcript playback, visual analytics, and a downloadable report.

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌────────────────────────────────────────────┐
│                  FRONTEND                  │
│  (HTML5 + CSS3 + Vanilla JS)               │
│  - Video Upload UI                         │
│  - Transcript Viewer                       │
│  - Analytics Dashboard                     │
│  - Report Export                           │
└────────────────┬───────────────────────────┘
                 │ REST API (JSON)
                 ▼
┌────────────────────────────────────────────┐
│              BACKEND API                   │
│  (Python + FastAPI)                        │
│  - /api/upload       → file handler        │
│  - /api/upload       → STT + analysis      │
│  - /api/analyze      → RAG + LLM pipeline  │
│  - /api/session/{id} → fetch results       │
└──────┬──────────────────────┬──────────────┘
       │                      │
       ▼                      ▼
┌─────────────┐    ┌──────────────────────────┐
│  Sarvam.ai  │    │  Groq API                │
│  STT API    │    │  (llama-3.1-70b-versatile│
│  saarika:v2 │    │   free tier)             │
└─────────────┘    └──────────┬───────────────┘
                              │
                   ┌──────────▼───────────────┐
                   │  ChromaDB (Vector Store)  │
                   │  Transcript chunks stored │
                   │  for retrieval-augmented  │
                   │  generation               │
                   └──────────────────────────┘
```

### 2.2 Data Flow

| Step | Action | Component |
|------|--------|-----------|
| 1 | User uploads video file | Frontend → Backend `/api/upload` |
| 2 | Backend stores video, extracts audio using FFmpeg | Backend service |
| 3 | Audio file sent to Sarvam.ai STT API | `sarvam_client.py` |
| 4 | Timestamped transcript returned | Sarvam.ai response |
| 5 | Transcript chunked and embedded (1024-token chunks, 128 overlap) | `vector_store.py` |
| 6 | Chunks stored in ChromaDB with session metadata | ChromaDB |
| 7 | 3 parallel Groq LLM calls (summary, tech terms, tips) + local metrics (WPM, filler words, vocab richness) | `llm_chain.py` |
| 8 | Structured JSON analysis compiled and stored in PostgreSQL | DB write |
| 9 | Frontend polls `/api/session/{id}` until complete | Polling / WebSocket |
| 10 | Dashboard rendered with all results | Frontend |

---

## 3. API Specification

### 3.1 POST `/api/upload`

**Description:** Accepts a video file and initiates the processing pipeline.

**Request:**
```
Content-Type: multipart/form-data
Body:
  - file: <binary video file>
  - language: string (optional, default: "auto")  // e.g. "hi-IN", "en-IN", "te-IN"
```

**Response:**
```json
{
  "session_id": "uuid-v4",
  "status": "processing",
  "estimated_duration_seconds": 45
}
```

**Status Codes:**
- `202 Accepted` — Processing started
- `400 Bad Request` — Unsupported file format
- `413 Payload Too Large` — File exceeds 500MB limit

---

### 3.2 GET `/api/session/{session_id}`

**Description:** Returns current processing status and results once complete.

**Response (Processing):**
```json
{
  "session_id": "uuid",
  "status": "processing",
  "stage": "transcribing",
  "progress_percent": 40
}
```

**Response (Complete):**
```json
{
  "session_id": "uuid",
  "status": "complete",
  "transcript": [
    {
      "start_ms": 0,
      "end_ms": 4200,
      "text": "Hello, my name is Aarav and today I'll be talking about my project.",
      "confidence": 0.97
    }
  ],
  "analysis": {
    "summary": "The speaker introduces themselves and explains a web scraping project...",
    "technical_terms": ["REST API", "Python", "BeautifulSoup", "PostgreSQL"],
    "project_keywords": ["web scraping", "data pipeline", "Flask dashboard"],
    "filler_words": {
      "total_count": 14,
      "percentage": 3.2,
      "breakdown": { "um": 5, "uh": 4, "basically": 3, "like": 2 }
    },
    "vocabulary_richness": {
      "total_words": 438,
      "unique_words": 201,
      "richness_score": 0.46
    },
    "pace": {
      "avg_wpm": 132,
      "rating": "ideal",
      "timeline": [
        { "segment": "0-60s", "wpm": 120 },
        { "segment": "60-120s", "wpm": 148 }
      ]
    },
    "sentiment": {
      "overall": "confident",
      "timeline": [
        { "segment": "0-60s", "tone": "neutral" },
        { "segment": "60-120s", "tone": "positive" }
      ]
    },
    "grammar_score": 82,
    "topics": ["Introduction", "Problem Statement", "Technical Architecture", "Results"],
    "improvement_tips": [
      "Reduce filler words — especially 'basically' (used 3 times).",
      "Your pace is ideal, but segment 2 was slightly rushed.",
      "Strong technical vocabulary — consider explaining 'REST API' for non-technical audiences.",
      "Use more transition phrases between topics for a smoother flow."
    ]
  }
}
```

---

### 3.3 POST `/api/analyze/ask`

**Description:** Ask a follow-up question about the video content (RAG Q&A mode).

**Request:**
```json
{
  "session_id": "uuid",
  "question": "What project did the speaker describe?"
}
```

**Response:**
```json
{
  "answer": "The speaker described a web scraping pipeline that collects data from e-commerce sites and stores it in PostgreSQL, visualized through a Flask dashboard.",
  "source_segments": [
    { "start_ms": 32000, "end_ms": 48000, "text": "...the scraper hits the product pages every 6 hours..." }
  ]
}
```

---

## 4. Sarvam.ai Integration

### 4.1 API Endpoint Used
`POST https://api.sarvam.ai/speech-to-text`

### 4.2 Request Format
```python
headers = {
    "api-subscription-key": SARVAM_API_KEY,
    "Content-Type": "multipart/form-data"
}
payload = {
    "model": "saarika:v2",          # Sarvam model
    "language_code": "en-IN",       # or auto-detect
    "with_timestamps": True,
    "with_disfluency": True         # keeps filler words intact
}
files = {
    "file": open("audio.wav", "rb")
}
```

### 4.3 Language Support Matrix

| Code | Language |
|------|----------|
| `en-IN` | Indian English |
| `hi-IN` | Hindi |
| `te-IN` | Telugu |
| `ta-IN` | Tamil |
| `kn-IN` | Kannada |
| `mr-IN` | Marathi |
| `auto` | Auto-detect |

### 4.4 Audio Preprocessing
- Video → Audio extraction via FFmpeg: `ffmpeg -i input.mp4 -vn -ar 16000 -ac 1 -f wav output.wav`
- 16kHz mono WAV is the optimal format for Sarvam.ai
- Files over 60 minutes are chunked into 25-minute segments

---

## 5. RAG Pipeline Specification

### 5.1 Chunking Strategy
- Chunk size: **1024 tokens**
- Overlap: **128 tokens**
- Each chunk tagged with: `session_id`, `start_ms`, `end_ms`, `chunk_index`

### 5.2 Embedding Model
- `all-MiniLM-L6-v2` — managed automatically by ChromaDB (no separate API key required)

### 5.3 Vector Store
- **ChromaDB** (local, persistent) — dev and MVP
- **Pinecone** — production option if scale requires it (not in MVP)

### 5.4 Prompt Templates

**Summary Prompt:**
```
You are an expert communication coach reviewing a student's spoken video.
The following is a transcript of what the student said:

{transcript}

Write a concise 4-6 sentence executive summary of the content.
Focus on: what topic was discussed, the main arguments or points made,
and the clarity of communication.
```

**Technical Terms Extraction Prompt:**
```
From the following transcript, extract all technical, domain-specific,
or project-related terms. Return a JSON array of strings.
Only include genuine technical vocabulary — ignore common words.

Transcript:
{transcript}

Return format: ["term1", "term2", ...]
```

**Filler Word Prompt:**
```
Analyze the following transcript for disfluency and filler words.
Count occurrences of: um, uh, like, basically, you know, so, right, okay,
actually, literally, kind of, sort of.
Return a JSON object with each word and its count.

Transcript:
{transcript}
```

**Improvement Tips Prompt:**
```
You are a professional communication and interview coach.
Given the following analysis of a student's spoken video:

- Filler word count: {filler_count} ({filler_percent}% of total words)
- Average pace: {wpm} words per minute
- Grammar score: {grammar_score}/100
- Technical terms detected: {tech_terms}
- Vocabulary richness: {richness_score}

Write 4-6 specific, actionable improvement tips personalized to this student.
Be encouraging but honest. Number the tips.
```

---

## 6. Frontend Component Specification

### 6.1 Upload Component
- Drag-and-drop zone + click-to-browse
- File type validation: `.mp4`, `.mov`, `.webm`, `.avi`, `.mkv`
- Max file size: 500MB
- Progress bar during upload
- Language selector dropdown (for Sarvam.ai)

### 6.2 Video Player Component
- HTML5 native `<video>` element
- Custom controls: play/pause, seek, volume, speed (0.5x–2x)
- Synchronized highlighting: active transcript line glows as video plays
- Click-to-seek: clicking a transcript word jumps to that time

### 6.3 Transcript Panel
- Full scrollable transcript with timestamps
- Color-coded highlights:
  - 🔴 Red underline — filler words
  - 🔵 Blue highlight — technical terms
  - 🟡 Yellow — low-confidence transcription segments
- Search bar to find any word in transcript
- Copy / Export as `.txt` or `.pdf`

### 6.4 Analysis Dashboard
- **Metrics Card Row:** Total words, Unique words, Filler %, WPM, Grammar Score
- **Radar Chart:** 6-axis — Vocabulary, Pace, Grammar, Confidence, Technical Depth, Clarity
- **Word Cloud:** Top 50 most significant words (excluding stopwords)
- **Pace Timeline Chart:** Line chart of WPM across the video duration
- **Filler Word Bar Chart:** Breakdown by filler word type
- **Topic Segments Timeline:** Visual block timeline showing detected topics
- **Technical Terms Tag Cloud:** All detected technical terms as clickable tags
- **Improvement Tips Card:** Numbered tips with icons

### 6.5 Q&A Panel (RAG Mode)
- Chat-like interface below the dashboard
- User types a question about the video
- Answer returned with source segment citation + seek button
- Suggested questions shown as quick chips: *"What project was discussed?"*, *"Summarize the technical approach"*, *"What were the weakest parts?"*

---

## 7. Database Schema

### Sessions Table
```sql
CREATE TABLE sessions (
  id UUID PRIMARY KEY,
  created_at TIMESTAMP,
  file_name VARCHAR(255),
  file_size_bytes BIGINT,
  duration_seconds INT,
  language_code VARCHAR(10),
  status VARCHAR(20),  -- 'uploading', 'transcribing', 'analyzing', 'complete', 'failed'
  sarvam_job_id VARCHAR(100),
  transcript_text TEXT,
  analysis_json JSONB
);
```

### Transcript Chunks Table
```sql
CREATE TABLE transcript_chunks (
  id SERIAL PRIMARY KEY,
  session_id UUID REFERENCES sessions(id),
  chunk_index INT,
  start_ms INT,
  end_ms INT,
  text TEXT,
  embedding_id VARCHAR(100)  -- ChromaDB/Pinecone reference
);
```

---

## 8. Error Handling

| Scenario | Frontend Behavior | Backend Response |
|----------|-------------------|------------------|
| Unsupported file type | Show red toast, prevent upload | 400 Bad Request |
| File > 500MB | Show size warning | 413 Payload Too Large |
| Sarvam.ai API failure | Show retry button | 502 Bad Gateway |
| LLM timeout (>60s) | Show partial results + retry for analysis | Partial 200 |
| No speech detected | Show "No speech found" message | 200 with empty transcript |
| Network loss during upload | Show progress recovery UI | — |

---

## 9. Performance Targets

| Metric | Target |
|--------|--------|
| Upload speed | Depends on network; show real-time progress |
| Audio extraction | < 10 seconds for a 10-minute video |
| Transcription turnaround | < 30 seconds per minute of audio |
| LLM analysis (all prompts) | < 20 seconds total |
| Frontend load time | < 2 seconds (first contentful paint) |
| Max supported video length | 60 minutes |

---

## 10. Security Considerations

- All uploaded files scanned for malicious content before processing
- Session IDs are UUIDs — non-guessable
- File storage uses signed URLs (time-limited access)
- API keys stored in environment variables, never in frontend code
- Rate limiting: 5 uploads per IP per hour (configurable)
- Uploaded videos deleted from server after 24 hours (configurable)
- HTTPS enforced in production
