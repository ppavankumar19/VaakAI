# SCOPE.md — VoiceIQ Project Scope

**Document Version:** 1.0  
**Status:** Draft  
**Last Updated:** March 2026  

---

## 1. Project Vision

VoiceIQ aims to democratize spoken communication feedback for students and job seekers in India and beyond. The core insight is that most students receive *zero* structured feedback on how they communicate verbally — in interviews, seminars, project presentations, or vivas. VoiceIQ automates this feedback loop using AI.

**The north star metric:** A student who uses VoiceIQ once should be able to identify at least 3 concrete things to improve in their spoken communication.

---

## 2. What Is In Scope

### ✅ Core Product (MVP)

| Feature | Priority | Notes |
|---------|----------|-------|
| Video file upload (.mp4, .mov, .webm) | P0 | Core input |
| Audio extraction from video | P0 | FFmpeg on backend |
| Speech-to-text via Sarvam.ai | P0 | Primary transcription API |
| Full timestamped transcript display | P0 | Core output |
| AI-generated summary of spoken content | P0 | LLM via LangChain |
| Technical/project keyword extraction | P0 | LLM prompt |
| Filler word detection and count | P0 | Rule-based + LLM |
| Improvement tips (personalized) | P0 | LLM prompt |
| Synchronized transcript + video player | P1 | Click-to-seek |
| Vocabulary richness score | P1 | Computed metric |
| Pace (WPM) analysis | P1 | Computed metric |
| Visual dashboard (charts) | P1 | Chart.js |
| Export transcript as .txt / .pdf | P1 | Download feature |
| RAG Q&A on video content | P2 | Ask questions about video |
| Grammar quality score | P2 | LLM grading |
| Sentiment/confidence tone analysis | P2 | LLM classification |
| Topic segmentation timeline | P2 | LLM + frontend viz |
| Multi-language support (Hindi, Telugu, etc.) | P2 | Sarvam.ai language codes |

### ✅ Backend & Infrastructure (MVP)

- FastAPI REST backend
- FFmpeg audio extraction service
- Sarvam.ai API integration
- LangChain RAG pipeline
- ChromaDB vector store
- PostgreSQL for session/transcript storage
- Basic file storage (local or S3)
- Session-based state management (no auth in MVP)

### ✅ Frontend (MVP)

- Single-page responsive web app
- Video upload with drag-and-drop
- Processing status indicator with stages
- Transcript viewer with highlights
- Analytics dashboard
- Export functionality

---

## 3. What Is Out of Scope (This Version)

### ❌ Explicitly Excluded from v1.0

| Feature | Reason Excluded |
|---------|----------------|
| User authentication & login | Adds complexity; MVP uses session-only model |
| Student profile & history | Requires user accounts — deferred to v2 |
| Real-time recording (no file upload) | Browser media capture API — Phase 2 |
| Mobile native app (iOS/Android) | Web-first approach for MVP |
| Comparison of two sessions side-by-side | Complex UI — Phase 2 |
| Interview question auto-detection + answer grading | Requires labeled dataset — Phase 3 |
| Live coaching / real-time feedback during recording | Streaming transcription pipeline — Phase 3 |
| Multi-speaker diarization (who said what) | Dependent on Sarvam.ai diarization support |
| Plagiarism / originality check | Out of scope for v1 |
| Custom rubric upload (for colleges) | B2B feature — Phase 3 |
| LMS/CMS integration (Moodle, Canvas) | Enterprise feature |
| Analytics across multiple students (admin dashboard) | Requires user accounts + batch data |
| AI-generated "ideal answer" suggestions | Requires domain-specific knowledge base |
| Video editing / annotation tools | Out of scope entirely |
| Payment / subscription system | Not needed for MVP |

---

## 4. Phased Delivery Plan

### Phase 1 — MVP (Weeks 1–6)

**Goal:** Working end-to-end pipeline. Upload a video, get a transcript and analysis.

**Deliverables:**
- [ ] Backend: File upload endpoint, FFmpeg audio extraction
- [ ] Backend: Sarvam.ai STT integration
- [ ] Backend: LLM analysis (summary + tech terms + filler words + tips)
- [ ] Frontend: Upload UI + processing status
- [ ] Frontend: Transcript display (plain, no sync)
- [ ] Frontend: Basic analysis results panel (text-only)
- [ ] Deployment: Working demo on localhost or basic cloud host

**Success Criteria:**
- Upload a 5-minute `.mp4` interview recording
- Receive full transcript within 3 minutes
- See summary, technical terms, filler words, and improvement tips

---

### Phase 2 — Enhanced UX (Weeks 7–12)

**Goal:** Make the product delightful to use. Add synchronization and visual analytics.

**Deliverables:**
- [ ] Synchronized video + transcript player (click-to-seek)
- [ ] Color-coded transcript highlights (fillers, tech terms, low-confidence)
- [ ] Full analytics dashboard (radar chart, WPM timeline, word cloud)
- [ ] Export transcript as PDF
- [ ] RAG Q&A panel
- [ ] Grammar score + sentiment analysis
- [ ] Topic segmentation display
- [ ] Multi-language support UI (language selector)
- [ ] Improved error handling + retry UX

**Success Criteria:**
- A student can click any line in the transcript and hear that moment
- Dashboard gives a clear visual summary of all metrics
- Student can ask "What did I explain poorly?" and get a useful answer

---

### Phase 3 — Depth Features (Weeks 13–20)

**Goal:** Add features that make VoiceIQ genuinely better than a human reviewer.

**Deliverables:**
- [ ] User authentication (email/Google OAuth)
- [ ] Session history — review past videos
- [ ] Comparison mode — compare two recordings of yourself
- [ ] Real-time recording mode (no file upload needed)
- [ ] Interview question detection (did the speaker answer the question completely?)
- [ ] Answer quality grading against standard rubrics
- [ ] Multi-speaker diarization (if supported by Sarvam.ai)
- [ ] Coach/reviewer dashboard (for trainers to review multiple students)

**Success Criteria:**
- A user can track their improvement over 5 sessions
- A trainer can upload 10 student videos and get a batch report

---

### Phase 4 — Scale & Integrations (Beyond Week 20)

**Goal:** Turn VoiceIQ into a platform.

**Deliverables:**
- [ ] Institutional/college dashboard
- [ ] Custom rubric builder for evaluators
- [ ] LMS integrations (Moodle, Canvas)
- [ ] API access for third-party integrations
- [ ] Mobile-responsive PWA
- [ ] Subscription model / pricing tiers

---

## 5. Dependencies & Assumptions

### External Dependencies

| Dependency | Purpose | Risk |
|------------|---------|------|
| Sarvam.ai API | Speech-to-text | Availability, pricing, rate limits |
| Anthropic Claude / OpenAI | LLM analysis | API cost, latency |
| FFmpeg | Audio extraction | Must be installed on server |
| ChromaDB / Pinecone | Vector store | Storage growth at scale |

### Assumptions

1. The primary use case is **recorded video** — not live streams
2. Video files will be **under 500MB** for MVP (1 hour max)
3. The speaker is the **primary audio source** (not audience noise)
4. **Sarvam.ai** is used as the primary STT engine; it may be swapped for Whisper or AssemblyAI in Phase 2 based on accuracy testing
5. No **user login** is required in MVP — sessions are anonymous with UUIDs
6. The primary audience speaks **Indian English or Indian languages** (hence Sarvam.ai)

---

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Sarvam.ai API goes down | Low | High | Fallback to OpenAI Whisper API |
| Transcription inaccurate for heavy accents | Medium | Medium | Allow user to edit transcript before analysis |
| LLM analysis costs too high at scale | Medium | High | Cache repeated analysis; use smaller models for simple tasks |
| Large video files cause timeout | Medium | High | Chunk processing; async job queue (Celery/Redis) |
| No speech in video | Low | Low | Graceful error state with clear message |
| Students upload inappropriate content | Low | High | File scan + content moderation on transcript |

---

## 7. Metrics for Success

### User Value Metrics
- **Transcript accuracy rate:** > 90% word accuracy on Indian English
- **Analysis relevance:** > 4/5 average user rating on improvement tips
- **Session completion rate:** > 70% of uploads reach the full analysis stage

### Technical Metrics
- **End-to-end processing time** for a 10-minute video: < 3 minutes
- **API uptime:** > 99% for backend
- **Error rate:** < 2% of sessions fail

### Product Metrics (Phase 2+)
- **Return usage rate:** % of users who upload a second video
- **Average sessions per user:** Target 3+ for meaningful improvement tracking
- **Feature adoption:** % of users who use RAG Q&A, export, comparison mode

---

## 8. Core User Journeys

### Journey 1: Pre-Interview Practice
> Priya records herself answering "Tell me about your project" on her phone. She uploads the `.mp4` to VoiceIQ. Within 2 minutes, she sees a full transcript and learns she said "basically" 9 times, her WPM was 160 (too fast), and her technical terms list is solid. She reads the improvement tips, records again, and improves her score.

### Journey 2: Post-Interview Reflection
> Rahul just completed a Google interview. He recorded it on his laptop. He uploads it and uses the RAG Q&A to ask "Did I explain the time complexity clearly?" The system retrieves the relevant segment and grades his explanation. He now knows what to improve for next time.

### Journey 3: Faculty Review
> Professor Sharma uploads a student's final-year project presentation to review communication quality. Without watching the whole video, she reads the 5-sentence summary, checks the vocabulary richness score (0.38 — below average), and notes the grammar score (71/100). She gives feedback in 3 minutes instead of 30.

---

## 9. Definition of Done (MVP)

A feature is "done" when:
1. It works end-to-end on a real 5-minute `.mp4` file
2. It handles the most common error states gracefully (no crashes)
3. It renders correctly on Chrome (desktop) at 1280px+ width
4. It has been manually tested by at least one person other than the developer

---

## 10. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | March 2026 | Initial draft |
