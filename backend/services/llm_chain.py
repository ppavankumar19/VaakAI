import json
import os
import re
import concurrent.futures
from pathlib import Path

from groq import Groq

# llama-3.1-70b-versatile: free tier, 128k context, strong instruction following
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def _load_prompt(name: str) -> str:
    path = Path(__file__).parent.parent / "prompts" / f"{name}_prompt.txt"
    return path.read_text(encoding="utf-8")


def _call_llm(prompt: str, max_tokens: int = 1024) -> str:
    response = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,  # lower temp = more consistent JSON/list output
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Local metric computation (no API calls)
# ---------------------------------------------------------------------------

FILLER_WORDS = [
    "you know", "kind of", "sort of",  # multi-word first (longer match wins)
    "um", "uh", "like", "basically", "so", "right",
    "okay", "actually", "literally",
]


def _compute_filler_words(text: str) -> dict:
    text_lower = text.lower()
    breakdown: dict[str, int] = {}
    for filler in FILLER_WORDS:
        pattern = r"\b" + re.escape(filler) + r"\b"
        count = len(re.findall(pattern, text_lower))
        if count:
            breakdown[filler] = count
    total = sum(breakdown.values())
    total_words = len(text.split())
    percentage = round(total / total_words * 100, 1) if total_words else 0.0
    return {"total_count": total, "percentage": percentage, "breakdown": breakdown}


def _compute_vocab_richness(text: str) -> dict:
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    total = len(words)
    unique = len(set(words))
    richness = round(unique / total, 2) if total else 0.0
    return {"total_words": total, "unique_words": unique, "richness_score": richness}


def _compute_pace(segments: list) -> dict:
    if not segments:
        return {"avg_wpm": 0, "rating": "unknown", "timeline": []}

    total_words = sum(len(s["text"].split()) for s in segments)
    start_ms = segments[0]["start_ms"]
    end_ms = segments[-1]["end_ms"]
    duration_min = (end_ms - start_ms) / 60_000

    if duration_min < 0.05:
        return {"avg_wpm": 0, "rating": "unknown", "timeline": []}

    avg_wpm = round(total_words / duration_min)

    if avg_wpm < 100:
        rating = "too_slow"
    elif avg_wpm > 180:
        rating = "too_fast"
    else:
        rating = "ideal"

    # Build 60-second WPM buckets
    timeline: list = []
    bucket_start_ms = start_ms
    bucket_words = 0

    for seg in segments:
        if seg["start_ms"] >= bucket_start_ms + 60_000:
            bucket_end_ms = bucket_start_ms + 60_000
            bucket_min = (bucket_end_ms - bucket_start_ms) / 60_000
            bucket_wpm = round(bucket_words / bucket_min) if bucket_min else 0
            label_s = round((bucket_start_ms - start_ms) / 1000)
            label_e = round((bucket_end_ms - start_ms) / 1000)
            timeline.append({"segment": f"{label_s}-{label_e}s", "wpm": bucket_wpm})
            bucket_start_ms = bucket_end_ms
            bucket_words = 0
        bucket_words += len(seg["text"].split())

    # Last partial bucket
    if bucket_words:
        remaining_min = (end_ms - bucket_start_ms) / 60_000
        bucket_wpm = round(bucket_words / remaining_min) if remaining_min else 0
        label_s = round((bucket_start_ms - start_ms) / 1000)
        label_e = round((end_ms - start_ms) / 1000)
        timeline.append({"segment": f"{label_s}-{label_e}s", "wpm": bucket_wpm})

    return {"avg_wpm": avg_wpm, "rating": rating, "timeline": timeline}


# ---------------------------------------------------------------------------
# LLM parsing helpers
# ---------------------------------------------------------------------------

def _parse_json_array(raw: str) -> list:
    """Extract a JSON array from an LLM response that may have surrounding text."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return []


def _parse_numbered_list(raw: str) -> list:
    """Extract numbered items like '1. tip' or '1) tip' from text."""
    tips = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^\d+[.)]\s+(.+)", line)
        if m:
            tips.append(m.group(1).strip())
    return tips or [line.strip() for line in raw.splitlines() if line.strip()]


def _parse_json_object(raw: str) -> dict:
    """Extract a JSON object from an LLM response that may have surrounding text."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _ms_to_mmss(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _format_timestamped(segments: list) -> str:
    """Format segments as '[M:SS] text' lines for the topics prompt."""
    return "\n".join(
        f"[{_ms_to_mmss(s['start_ms'])}] {s['text']}"
        for s in segments
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_analysis(transcript_text: str, segments: list) -> dict:
    """
    Run all analysis passes on the transcript.
    Local metrics are computed inline; Groq LLM calls run in parallel.
    """
    filler_words = _compute_filler_words(transcript_text)
    vocab_richness = _compute_vocab_richness(transcript_text)
    pace = _compute_pace(segments)
    timestamped_transcript = _format_timestamped(segments)

    summary_prompt = _load_prompt("summary").format(transcript=transcript_text)
    tech_terms_prompt = _load_prompt("tech_terms").format(transcript=transcript_text)
    grammar_prompt = _load_prompt("grammar").format(transcript=transcript_text)
    sentiment_prompt = _load_prompt("sentiment").format(transcript=transcript_text)
    topics_prompt = _load_prompt("topics").format(timestamped_transcript=timestamped_transcript)

    # Run first 5 calls in parallel; tips needs grammar_score so runs after
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        f_summary = pool.submit(_call_llm, summary_prompt, 512)
        f_tech = pool.submit(_call_llm, tech_terms_prompt, 512)
        f_grammar = pool.submit(_call_llm, grammar_prompt, 64)
        f_sentiment = pool.submit(_call_llm, sentiment_prompt, 512)
        f_topics = pool.submit(_call_llm, topics_prompt, 512)

        summary_text = f_summary.result()
        tech_raw = f_tech.result()
        grammar_raw = f_grammar.result()
        sentiment_raw = f_sentiment.result()
        topics_raw = f_topics.result()

    tech_terms = _parse_json_array(tech_raw)
    grammar_obj = _parse_json_object(grammar_raw)
    grammar_score = int(grammar_obj.get("score", 0)) if grammar_obj else None
    sentiment = _parse_json_object(sentiment_raw) or None
    topics = _parse_json_array(topics_raw)

    tips_prompt = _load_prompt("improvement_tips").format(
        filler_count=filler_words["total_count"],
        filler_percent=filler_words["percentage"],
        wpm=pace["avg_wpm"],
        grammar_score=grammar_score if grammar_score is not None else "N/A",
        tech_terms=", ".join(tech_terms[:8]) if tech_terms else "none detected",
        richness_score=vocab_richness["richness_score"],
    )
    tips_raw = _call_llm(tips_prompt, 1024)
    improvement_tips = _parse_numbered_list(tips_raw)

    return {
        "summary": summary_text.strip(),
        "technical_terms": tech_terms,
        "project_keywords": tech_terms[:5],
        "filler_words": filler_words,
        "vocabulary_richness": vocab_richness,
        "pace": pace,
        "sentiment": sentiment,
        "grammar_score": grammar_score,
        "topics": topics if topics else None,
        "improvement_tips": improvement_tips,
    }
