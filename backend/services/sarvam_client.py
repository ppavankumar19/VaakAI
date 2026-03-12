import os
from pathlib import Path
import httpx


SARVAM_API_URL = "https://api.sarvam.ai/speech-to-text"


def transcribe_audio(audio_path: str, language_code: str = "en-IN") -> list:
    """
    Send WAV audio to Sarvam.ai saarika:v2 and return transcript segments.

    Returns list of:
        {"start_ms": int, "end_ms": int, "text": str, "confidence": float}

    NOTE: Sarvam.ai returns word-level timestamps in data["timestamps"].
    Each entry: {"word": str, "start": float (seconds), "end": float (seconds)}
    This parser groups words into sentence-length segments.
    If their API response shape changes, update _parse_response().
    """
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise ValueError("SARVAM_API_KEY environment variable is not set")

    # "auto" is not a valid Sarvam language code — fall back to Indian English
    lang = language_code if language_code != "auto" else "en-IN"

    with open(audio_path, "rb") as f:
        response = httpx.post(
            SARVAM_API_URL,
            headers={"api-subscription-key": api_key},
            data={
                "model": "saarika:v2",
                "language_code": lang,
                "with_timestamps": "true",
                "with_disfluency": "true",  # preserves filler words intact
            },
            files={"file": (Path(audio_path).name, f, "audio/wav")},
            timeout=300.0,
        )

    response.raise_for_status()
    return _parse_response(response.json())


def _parse_response(data: dict) -> list:
    transcript_text: str = data.get("transcript", "")
    word_timestamps: list = data.get("timestamps", [])

    if not word_timestamps:
        # Sarvam returned transcript only — no word timestamps
        if transcript_text.strip():
            return [{"start_ms": 0, "end_ms": 0, "text": transcript_text.strip(), "confidence": 1.0}]
        return []

    # Group words into sentence-level segments.
    # Split on sentence-ending punctuation or every 15 words (whichever comes first).
    segments = []
    current_words: list = []
    current_start_ms: int | None = None

    for entry in word_timestamps:
        word = entry.get("word", "").strip()
        if not word:
            continue

        start_ms = int(entry.get("start", 0) * 1000)
        end_ms = int(entry.get("end", 0) * 1000)

        if current_start_ms is None:
            current_start_ms = start_ms

        current_words.append({"word": word, "end_ms": end_ms})

        ends_sentence = word.rstrip().endswith((".", "?", "!"))
        if ends_sentence or len(current_words) >= 15:
            text = " ".join(w["word"] for w in current_words)
            segments.append({
                "start_ms": current_start_ms,
                "end_ms": current_words[-1]["end_ms"],
                "text": text,
                "confidence": 0.95,  # Sarvam doesn't expose per-segment confidence
            })
            current_words = []
            current_start_ms = None

    # Flush remaining words
    if current_words:
        text = " ".join(w["word"] for w in current_words)
        segments.append({
            "start_ms": current_start_ms or 0,
            "end_ms": current_words[-1]["end_ms"],
            "text": text,
            "confidence": 0.95,
        })

    return segments
